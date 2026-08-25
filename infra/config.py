import os
import yaml
import re
from copy import deepcopy
from pathlib import Path
from dotenv import load_dotenv

import pulumi

from defaults import (
    DEFAULT_BOOTSTRAP,
    DEFAULT_REGION,
    DEFAULT_CLUSTER_NAME,
    DEFAULT_WORKER_NODE_PLAN,
    DEFAULT_WORKER_NODE_COUNT,
    DEFAULT_DNS_TTL,
)
from errors import (
    ConfigurationError,
    ConfigurationScope,
)
from schema import (
    ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_KEYS,
    ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_IMAGE_KEYS,
    ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_AUTH_KEYS,
    ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_AUTH_OIDC_KEYS,
    ALLOWED_APPLICATION_KEYS,
    ALLOWED_DATABASE_KEYS,
    ALLOWED_AUTH_KEYS,
    ALLOWED_AUTH_OIDC_KEYS,
    ALLOWED_CHART_KEYS,
    ALLOWED_HELM_PARAMETER_PATH_KEYS,
    EXPECTED_HELM_PARAMETER_PATH_INDEX_COUNTS,
    IMAGE_HELM_PARAMETER_PATH_KEYS,
    DATABASE_IDENTIFIER_HELM_PARAMETER_PATH_KEYS,
    INGRESS_HELM_PARAMETER_PATH_KEYS,
    OIDC_HELM_PARAMETER_PATH_KEYS,
    REQUIRED_OIDC_SECRET_REQUIREMENTS,
)
from constants import (
    HELM_PATH_INDEX_PLACEHOLDER
)

INFRA_DIR = Path(__file__).parent
BASE_DIR = INFRA_DIR.parent

SECRETS_FILE = INFRA_DIR / "secrets.local.env"
APPLICATION_CATALOG_FILE = BASE_DIR / "apps" / "apps.yaml"

APPLICATION_IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_]*$"
MIN_DNS_TTL = 60


def load_application_catalog() -> dict:

    with APPLICATION_CATALOG_FILE.open("r", encoding="utf-8") as file_handle:
        return yaml.safe_load(file_handle)


class Settings:

    def __init__(self) -> None:

        load_dotenv(dotenv_path=SECRETS_FILE, override=False)

        self.vultr_api_key = os.environ.get("VULTR_API_KEY")
        self.postgresql_superuser_password = os.environ.get("POSTGRESQL_SUPERUSER_PASSWORD")
        self.postgresql_app_password = os.environ.get("POSTGRESQL_APP_PASSWORD")
        self.bootstrap_confirmed = os.environ.get("VULTR_KUBERNETES_PLATFORM_BOOTSTRAP_CONFIRM")

        config = pulumi.Config()
        bootstrap = config.get_bool("bootstrap")

        self.repository_url = config.require("repository_url")
        self.bootstrap = DEFAULT_BOOTSTRAP if bootstrap is None else bootstrap
        self.region = config.get("region") or DEFAULT_REGION
        self.cluster_name = config.get("cluster_name") or DEFAULT_CLUSTER_NAME
        self.kubernetes_version = config.require("kubernetes_version")
        self.worker_node_plan = config.get("worker_node_plan") or DEFAULT_WORKER_NODE_PLAN
        self.worker_node_count = config.get_int("worker_node_count") or DEFAULT_WORKER_NODE_COUNT
        self.dns_ttl = config.get_int("dns_ttl") or DEFAULT_DNS_TTL
        self.domains = config.require_object("domains")
        self.primary_domain_name = self.domains[0].get("name") if self.domains else None

        self.application_catalog = load_application_catalog()

        self.validate()

    @staticmethod
    def identifier_to_slug(identifier: str) -> str:

        return identifier.lower().replace("_", "-")

    @staticmethod
    def identifier_to_display_name(identifier: str) -> str:

        return identifier.replace("_", " ").title()

    @staticmethod
    def domain_to_slug(domain_name: str) -> str:

        return domain_name.lower().replace(".", "-")

    @staticmethod
    def domain_to_identifier(domain_name: str) -> str:

        return domain_name.lower().replace(".", "_")

    def get_domain_secret_env_name(self, application, domain_name, secret_name) -> str:

        domain_identifier = self.domain_to_identifier(domain_name)

        env_name = (
            f"{application}_"
            f"{domain_identifier}_"
            f"{secret_name}"
        )

        return env_name.upper()

    def get_domain_secret(self, application, domain_name, secret_name) -> str | None:

        return os.environ.get(self.get_domain_secret_env_name(application, domain_name, secret_name))

    def domain_applications(self, domain_name: str) -> dict:

        domain = next(domain for domain in self.domains if domain["name"] == domain_name)

        application_configs = {}

        for domain_application_entry in domain.get("applications", []):

            application_name, application_domain_deployment_config = self.normalize_domain_application_entry(domain_application_entry)

            application_config = deepcopy(self.application_catalog[application_name])

            self.merge_configuration(configuration=application_config, configuration_update=application_domain_deployment_config)

            application_config["host_prefix"] = application_domain_deployment_config.get("host_prefix", application_config["default_host_prefix"])

            application_configs[application_name] = application_config

        return application_configs

    @staticmethod
    def normalize_domain_application_entry(domain_application_entry) -> tuple[str, dict]:

        if isinstance(domain_application_entry, str):
            return domain_application_entry, {}

        application_name, application_domain_deployment_config = next(iter(domain_application_entry.items()))

        if application_domain_deployment_config is None:
            application_domain_deployment_config = {}

        return application_name, application_domain_deployment_config

    @staticmethod
    def merge_configuration(configuration: dict, configuration_update: dict) -> None:

        for key, update_value in configuration_update.items():

            configured_value = configuration.get(key)

            if isinstance(configured_value, dict) and isinstance(update_value, dict):
                Settings.merge_configuration(configuration=configured_value, configuration_update=update_value)
            else:
                configuration[key] = deepcopy(update_value)

    def validate_prerequisites(self) -> None:

        required_prerequisites = [("VULTR_API_KEY", self.vultr_api_key)]

        if not self.bootstrap:
            required_prerequisites.extend(
                [
                    ("POSTGRESQL_SUPERUSER_PASSWORD", self.postgresql_superuser_password),
                    ("POSTGRESQL_APP_PASSWORD", self.postgresql_app_password),
                ]
            )
        elif not self.bootstrap_confirmed:
            raise ConfigurationError(
                message="Bootstrap mode is enabled without explicit confirmation.",
                hint=(
                    "Set VULTR_KUBERNETES_PLATFORM_BOOTSTRAP_CONFIRM environment variable "
                    "(WARNING: set only during the initial platform bootstrap)."
                ),
            )

        for env_name, value in required_prerequisites:
            if not value:
                raise ConfigurationError(
                    message=f"{env_name} is not set.",
                    hint=f"Create {SECRETS_FILE.name} or set the environment variable.",
                )

        if self.worker_node_count != 1:
            raise ConfigurationError(
                message=f"Configured worker_node_count is {self.worker_node_count}.",
                hint="This low-cost DNS setup expects exactly one VKE worker node.",
            )

    def validate_platform_config(self) -> None:

        if self.dns_ttl < MIN_DNS_TTL:
            raise ConfigurationError(
                message=f"Configured dns_ttl is {self.dns_ttl}.",
                hint=f"Set dns_ttl to at least {MIN_DNS_TTL} seconds.",
            )

        if not self.domains:
            raise ConfigurationError(
                message="No domains are configured.",
                hint="Configure at least one domain.",
            )

        if not self.primary_domain_name:
            raise ConfigurationError(
                message="The primary domain has no name.",
                hint="Set the 'name' field on the first domain entry.",
            )

        if not isinstance(self.application_catalog, dict):
            raise ConfigurationError(
                message="Invalid application catalog format.",
                hint=f"{APPLICATION_CATALOG_FILE.name} must contain a dictionary of supported applications.",
            )

    def validate_domain_config(self, domain: dict) -> None:

        domain_name = domain.get("name")

        if not domain_name:
            raise ConfigurationError(
                message="A domain entry has no name.",
                hint="Add a non-empty 'name' value to each domain entry.",
            )

        if not isinstance(domain.get("apex", True), bool):
            raise ConfigurationError(
                message="apex is not a Boolean value.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Set apex to true or false.",
            )

        if not isinstance(domain.get("wildcard", False), bool):
            raise ConfigurationError(
                message="wildcard is not a Boolean value.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Set wildcard to true or false.",
            )

        self.validate_domain_dns_config(domain=domain, domain_name=domain_name)

        if self.bootstrap:
            return

        domain_application_entries = domain.get("applications", [])

        if not isinstance(domain_application_entries, list):
            raise ConfigurationError(
                message="applications is not a list.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Define applications as a YAML list or omit it when no applications are required.",
            )

        configured_application_names = set()
        configured_oidc_providers = set()

        for domain_application_entry in domain_application_entries:

            self.validate_domain_application_entry(domain_application_entry=domain_application_entry, domain_name=domain_name)

            application_name, application_domain_deployment_config = self.normalize_domain_application_entry(domain_application_entry)

            if application_name in configured_application_names:
                raise ConfigurationError(
                    message=f"Application '{application_name}' is configured more than once.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint="Configure each application only once per domain.",
                )

            configured_application_names.add(application_name)

            if application_name not in self.application_catalog:
                raise ConfigurationError(
                    message=f"Application '{application_name}' is not present in the application catalog.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint=f"Add '{application_name}' to {APPLICATION_CATALOG_FILE.name} or remove it from this domain's applications list.",
                )

            application_config = self.application_catalog[application_name]

            self.validate_application_config(application_name=application_name, application_config=application_config, domain_name=domain_name)

            self.validate_application_domain_deployment_config(application_name=application_name, application_config=application_config, application_domain_deployment_config=application_domain_deployment_config, domain_name=domain_name)

            authentication_config = application_domain_deployment_config.get("authentication", {})
            oidc_config = authentication_config.get("oidc", {})

            if oidc_config:
                configured_oidc_providers.add(oidc_config["identity_provider"])

        missing_oidc_providers = configured_oidc_providers - configured_application_names
        if missing_oidc_providers:
            raise ConfigurationError(
                message=f"OIDC provider application(s) are not deployed on this domain: {', '.join(sorted(missing_oidc_providers))}.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Add the missing OIDC provider application(s) to this domain's applications list.",
            )

    def validate_domain_application_entry(self, domain_application_entry, domain_name: str) -> None:

        if isinstance(domain_application_entry, str):

            if not domain_application_entry:
                raise ConfigurationError(
                    message="An application entry has no name.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint="Use a non-empty application identifier.",
                )

            return

        if not isinstance(domain_application_entry, dict):
            raise ConfigurationError(
                message="An application entry is neither a string nor a dictionary.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Define an application as a name or as a single-key mapping containing domain deployment configuration.",
            )

        if len(domain_application_entry) != 1:
            raise ConfigurationError(
                message="An application entry does not contain exactly one application.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Define each application as a single-key mapping.",
            )

        application_name, application_domain_deployment_config = next(iter(domain_application_entry.items()))

        if not isinstance(application_name, str) or not application_name:
            raise ConfigurationError(
                message="An application entry has an invalid name.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Use a non-empty application identifier as the mapping key.",
            )

        if application_domain_deployment_config is not None and not isinstance(application_domain_deployment_config, dict):
            raise ConfigurationError(
                message=f"Domain deployment configuration for application '{application_name}' is not a dictionary.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Define the application domain deployment configuration as a YAML mapping.",
            )

    def validate_application_domain_deployment_config(self, application_name: str, application_config: dict, application_domain_deployment_config: dict, domain_name: str) -> None:

        self.validate_allowed_keys("application domain deployment", application_domain_deployment_config, ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_KEYS, application_name)

        host_prefix = application_domain_deployment_config.get("host_prefix")

        if host_prefix is not None and (not isinstance(host_prefix, str) or not host_prefix.strip()):
            raise ConfigurationError(
                message="host_prefix is not a non-empty string.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Set host_prefix to a non-empty hostname prefix.",
            )

        image = application_domain_deployment_config.get("image", {})

        if not isinstance(image, dict):
            raise ConfigurationError(
                message="image is not a dictionary.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Define image as a YAML mapping containing repository and tag.",
            )

        self.validate_allowed_keys("image", image, ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_IMAGE_KEYS, application_name)

        if "image" in application_domain_deployment_config:

            for image_key in ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_IMAGE_KEYS:

                image_value = image.get(image_key)

                if not isinstance(image_value, str) or not image_value.strip():
                    raise ConfigurationError(
                        message=f"image.{image_key} is not a non-empty string.",
                        scope=ConfigurationScope.DOMAIN,
                        name=domain_name,
                        hint=f"Set image.{image_key} to a non-empty string.",
                    )

            helm_parameter_paths = application_config.get("helm_parameter_paths", {})

            configured_image_parameter_paths = IMAGE_HELM_PARAMETER_PATH_KEYS & set(helm_parameter_paths)

            if configured_image_parameter_paths != IMAGE_HELM_PARAMETER_PATH_KEYS:

                missing_parameter_paths = IMAGE_HELM_PARAMETER_PATH_KEYS - configured_image_parameter_paths

                raise ConfigurationError(
                    message="Image deployment configuration is enabled, but the application catalog does not define all required image Helm parameter paths.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint=f"Configure the following missing Helm parameter path(s) for '{application_name}': {', '.join(sorted(missing_parameter_paths))}.",
                )

        authentication = application_domain_deployment_config.get("authentication", {})

        if not isinstance(authentication, dict):
            raise ConfigurationError(
                message="authentication is not a dictionary.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Define authentication as a YAML mapping.",
            )

        self.validate_allowed_keys("authentication", authentication, ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_AUTH_KEYS, application_name)

        oidc = authentication.get("oidc", {})

        if not isinstance(oidc, dict):
            raise ConfigurationError(
                message="authentication.oidc is not a dictionary.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Define authentication.oidc as a YAML mapping.",
            )

        self.validate_allowed_keys("authentication.oidc", oidc, ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_AUTH_OIDC_KEYS, application_name)

        if "oidc" in authentication:

            application_auth_config = application_config.get("authentication", {})

            if "oidc" not in application_auth_config:
                raise ConfigurationError(
                    message="OIDC authentication is enabled for this deployment, but the application catalog does not define OIDC support.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Add authentication.oidc to the application catalog entry or remove authentication.oidc from the domain deployment configuration.",
                )

            provider = oidc.get("identity_provider")

            if not isinstance(provider, str) or not provider.strip():
                raise ConfigurationError(
                    message="authentication.oidc.identity_provider is not a non-empty string.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint="Set authentication.oidc.identity_provider to a non-empty application identifier.",
                )

            if provider not in self.application_catalog:
                raise ConfigurationError(
                    message=f"OIDC provider application '{provider}' is not present in the application catalog.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint=f"Add '{provider}' to {APPLICATION_CATALOG_FILE.name} or configure a supported OIDC provider application.",
                )

    def validate_allowed_keys(self, section_name: str, configuration: dict, allowed_keys: set[str], application_name: str) -> None:

        unknown_keys = set(configuration) - allowed_keys

        if unknown_keys:
            raise ConfigurationError(
                message=f"Unknown key(s) in '{section_name}': {', '.join(sorted(unknown_keys))}.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint=f"Remove the unsupported key(s) from the '{section_name}' section.",
            )

    def validate_application_config(self, application_name: str, application_config: dict, domain_name: str) -> None:

        if not isinstance(application_config, dict):
            raise ConfigurationError(
                message="Configuration must be a dictionary.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint=f"Define '{application_name}' as a YAML mapping in {APPLICATION_CATALOG_FILE.name}.",
            )

        if not re.fullmatch(APPLICATION_IDENTIFIER_PATTERN, application_name):
            raise ConfigurationError(
                message="Application identifier is invalid.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Use only lowercase letters, digits and underscores. The name must start with a lowercase letter.",
            )

        self.validate_allowed_keys("application", application_config, ALLOWED_APPLICATION_KEYS, application_name)

        default_host_prefix = application_config.get("default_host_prefix")

        if not isinstance(default_host_prefix, str) or not default_host_prefix.strip():

            raise ConfigurationError(
                message="default_host_prefix is not a non-empty string.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Set default_host_prefix to a hostname prefix, such as 'www', 'auth' or 'dashboard'.",
            )

        secret_requirements = application_config.get("secret_requirements", [])

        if not isinstance(secret_requirements, list):
            raise ConfigurationError(
                message="secret_requirements is not a list.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Define secret_requirements as a YAML list or omit it when no application secrets are required.",
            )

        if len(secret_requirements) != len(set(secret_requirements)):
            raise ConfigurationError(
                message="secret_requirements contains duplicates.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="List each secret requirement only once.",
            )

        if secret_requirements and not application_config.get("namespace", False):
            raise ConfigurationError(
                message="secret_requirements are defined, but namespace is not enabled.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Set namespace to true or remove secret_requirements.",
            )

        for secret_name in secret_requirements:

            if not isinstance(secret_name, str) or not secret_name.strip():
                raise ConfigurationError(
                    message="A secret requirement is not a non-empty string.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Use a non-empty string for every entry in secret_requirements.",
                )

            env_name = self.get_domain_secret_env_name(application=application_name, domain_name=domain_name, secret_name=secret_name)

            if not os.environ.get(env_name):
                raise ConfigurationError(
                    message=f"{env_name} is not set.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint=f"Add {env_name} to {SECRETS_FILE.name} or set the environment variable.",
                )

        database_config = application_config.get("database", {})

        if not isinstance(database_config, dict):
            raise ConfigurationError(
                message="database is not a dictionary.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Define database as a YAML mapping or omit it when no database is required.",
            )

        self.validate_allowed_keys("database", database_config, ALLOWED_DATABASE_KEYS, application_name)

        database_enabled = database_config.get("enabled", False)

        if not isinstance(database_enabled, bool):
            raise ConfigurationError(
                message="database.enabled is not a Boolean value.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Set database.enabled to true or false.",
            )

        connection_url_secret_enabled = database_config.get("connection_url_secret", False)

        if not isinstance(connection_url_secret_enabled, bool):
            raise ConfigurationError(
                message="database.connection_url_secret is not a Boolean value.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Set database.connection_url_secret to true or false.",
            )

        if connection_url_secret_enabled:

            if not database_enabled:
                raise ConfigurationError(
                    message="database.connection_url_secret is enabled while database.enabled is disabled.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Set database.enabled to true or disable database.connection_url_secret.",
                )

            if not application_config.get("namespace", False):
                raise ConfigurationError(
                    message="database.connection_url_secret is enabled, but namespace is not enabled.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Set namespace to true or disable database.connection_url_secret.",
                )

        authentication_config = application_config.get("authentication", {})

        if not isinstance(authentication_config, dict):
            raise ConfigurationError(
                message="authentication is not a dictionary.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Define authentication as a YAML mapping or omit it when no authentication integration is supported.",
            )

        self.validate_allowed_keys("authentication", authentication_config, ALLOWED_AUTH_KEYS, application_name)

        oidc_config = authentication_config.get("oidc", {})

        if not isinstance(oidc_config, dict):
            raise ConfigurationError(
                message="authentication.oidc is not a dictionary.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Define authentication.oidc as a YAML mapping.",
            )

        self.validate_allowed_keys("authentication.oidc", oidc_config, ALLOWED_AUTH_OIDC_KEYS, application_name)

        if "oidc" in authentication_config:

            oidc_display_name = oidc_config.get("display_name")

            if oidc_display_name is not None and (not isinstance(oidc_display_name, str) or not oidc_display_name.strip()):
                raise ConfigurationError(
                    message="authentication.oidc.display_name is not a non-empty string.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Set authentication.oidc.display_name to a non-empty display name or omit it to use the identity provider name instead.",
                )

            oidc_secret_requirements = oidc_config.get("secret_requirements", [])

            if not isinstance(oidc_secret_requirements, list):
                raise ConfigurationError(
                    message="authentication.oidc.secret_requirements is not a list.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Define authentication.oidc.secret_requirements as a YAML list.",
                )

            if len(oidc_secret_requirements) != len(set(oidc_secret_requirements)):
                raise ConfigurationError(
                    message="authentication.oidc.secret_requirements contains duplicates.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="List each OIDC secret requirement only once.",
                )

            for secret_name in oidc_secret_requirements:

                if not isinstance(secret_name, str) or not secret_name.strip():
                    raise ConfigurationError(
                        message="An OIDC secret requirement is not a non-empty string.",
                        scope=ConfigurationScope.APPLICATION,
                        name=application_name,
                        hint="Use a non-empty string for every entry in authentication.oidc.secret_requirements.",
                    )

            configured_oidc_secret_requirements = set(oidc_secret_requirements)

            if configured_oidc_secret_requirements != REQUIRED_OIDC_SECRET_REQUIREMENTS:

                missing_secret_requirements = REQUIRED_OIDC_SECRET_REQUIREMENTS - configured_oidc_secret_requirements
                additional_secret_requirements = configured_oidc_secret_requirements - REQUIRED_OIDC_SECRET_REQUIREMENTS

                hints = []

                if missing_secret_requirements:
                    hints.append(f"Add the following secret requirement(s): {', '.join(sorted(missing_secret_requirements))}.")

                if additional_secret_requirements:
                    hints.append(f"Remove the following unsupported secret requirement(s): {', '.join(sorted(additional_secret_requirements))}.")

                raise ConfigurationError(
                    message="authentication.oidc.secret_requirements is invalid.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint=" ".join(hints),
                )

            oidc_helm_parameter_paths = oidc_config.get("helm_parameter_paths", {})

            if not isinstance(oidc_helm_parameter_paths, dict):
                raise ConfigurationError(
                    message="authentication.oidc.helm_parameter_paths is not a dictionary.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Define authentication.oidc.helm_parameter_paths as a YAML mapping.",
                )

            self.validate_allowed_keys("authentication.oidc.helm_parameter_paths", oidc_helm_parameter_paths, OIDC_HELM_PARAMETER_PATH_KEYS, application_name)

            for parameter_name, parameter_path in oidc_helm_parameter_paths.items():

                if not isinstance(parameter_path, str) or not parameter_path.strip():
                    raise ConfigurationError(
                        message=f"authentication.oidc.helm_parameter_paths.{parameter_name} is not a non-empty string.",
                        scope=ConfigurationScope.APPLICATION,
                        name=application_name,
                        hint="Set the parameter path to the corresponding non-empty Helm values path.",
                    )

                expected_index_count = EXPECTED_HELM_PARAMETER_PATH_INDEX_COUNTS[parameter_name]
                actual_index_count = parameter_path.count(HELM_PATH_INDEX_PLACEHOLDER)

                if actual_index_count != expected_index_count:
                    raise ConfigurationError(
                        message=f"authentication.oidc.helm_parameter_paths.{parameter_name} contains {actual_index_count} '{HELM_PATH_INDEX_PLACEHOLDER}' index placeholder(s).",
                        scope=ConfigurationScope.APPLICATION,
                        name=application_name,
                        hint=f"Use exactly {expected_index_count} '{HELM_PATH_INDEX_PLACEHOLDER}' index placeholder(s) in this parameter path.",
                    )

        chart_config = application_config["chart"]

        if not isinstance(chart_config, dict):
            raise ConfigurationError(
                message="chart is not a dictionary.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Define chart as a YAML mapping containing repository_url and version.",
            )

        self.validate_allowed_keys("chart", chart_config, ALLOWED_CHART_KEYS, application_name)

        chart_source = chart_config.get("source", "remote")

        if chart_source not in {"remote", "local"}:
            raise ConfigurationError(
                message=f"chart.source has unsupported value '{chart_source}'.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Set chart.source to 'remote' or 'local', or omit it to use the default ('remote').",
            )

        if chart_source == "remote":
            for key in ("repository_url", "version"):
                value = chart_config.get(key)
                if not isinstance(value, str) or not value.strip():
                    raise ConfigurationError(
                        message=f"chart.{key} is not a non-empty string.",
                        scope=ConfigurationScope.APPLICATION,
                        name=application_name,
                        hint=f"Set chart.{key} for a remote Helm chart.",
                    )
        else:
            for key in ("repository_url", "version"):
                if key in chart_config:
                    raise ConfigurationError(
                        message=f"chart.{key} is configured for a local Helm chart.",
                        scope=ConfigurationScope.APPLICATION,
                        name=application_name,
                        hint=f"Remove chart.{key}; local charts are loaded from apps/{application_name}/.",
                    )

        helm_parameter_paths = application_config.get("helm_parameter_paths", {})

        if not isinstance(helm_parameter_paths, dict):
            raise ConfigurationError(
                message="helm_parameter_paths is not a dictionary.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Define helm_parameter_paths as a YAML mapping or omit it when no generated Helm parameters are required.",
            )

        self.validate_allowed_keys("helm_parameter_paths", helm_parameter_paths, ALLOWED_HELM_PARAMETER_PATH_KEYS, application_name)

        for parameter_name, parameter_path in helm_parameter_paths.items():

            if not isinstance(parameter_path, str) or not parameter_path.strip():
                raise ConfigurationError(
                    message=f"helm_parameter_paths.{parameter_name} is not a non-empty string.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Set the parameter path to the corresponding non-empty Helm values path.",
                )

            expected_index_count = EXPECTED_HELM_PARAMETER_PATH_INDEX_COUNTS[parameter_name]
            actual_index_count = parameter_path.count(HELM_PATH_INDEX_PLACEHOLDER)

            if actual_index_count != expected_index_count:
                raise ConfigurationError(
                    message=f"helm_parameter_paths.{parameter_name} contains {actual_index_count} '{HELM_PATH_INDEX_PLACEHOLDER}' index placeholder(s).",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint=f"Use exactly {expected_index_count} '{HELM_PATH_INDEX_PLACEHOLDER}' index placeholder(s) in this parameter path."
                )

        for parameter_name in DATABASE_IDENTIFIER_HELM_PARAMETER_PATH_KEYS:

            if parameter_name in helm_parameter_paths and not database_enabled:
                raise ConfigurationError(
                    message=f"helm_parameter_paths.{parameter_name} is configured while database.enabled is disabled.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint=f"Set database.enabled to true or remove helm_parameter_paths.{parameter_name}.",
                )

        configured_ingress_parameters = INGRESS_HELM_PARAMETER_PATH_KEYS & set(helm_parameter_paths)

        if configured_ingress_parameters and configured_ingress_parameters != INGRESS_HELM_PARAMETER_PATH_KEYS:
            missing_parameters = INGRESS_HELM_PARAMETER_PATH_KEYS - configured_ingress_parameters
            raise ConfigurationError(
                message="Ingress Helm parameter paths are incomplete.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint=f"Configure the following missing parameter path(s): {', '.join(sorted(missing_parameters))}.",
            )

    def validate_domain_dns_config(self, domain: dict, domain_name: str) -> None:

        domain_ttl = domain.get("ttl")

        if domain_ttl is not None and domain_ttl < MIN_DNS_TTL:
            raise ConfigurationError(
                message=f"ttl is less than {MIN_DNS_TTL} seconds.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint=f"Set ttl to at least {MIN_DNS_TTL} seconds.",
            )

        for record_index, record in enumerate(domain.get("records", []), start=1):

            record_name = record.get("name")

            if not record_name:
                raise ConfigurationError(
                    message=f"DNS record #{record_index} has no name.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint="Set the name for every DNS record.",
                )

            if not record.get("type"):
                raise ConfigurationError(
                    message=f"DNS record '{record_name}' has no type.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint="Set the type for every DNS record.",
                )

            if not record.get("data"):
                raise ConfigurationError(
                    message=f"DNS record '{record_name}' has no data.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint="Set the data for every DNS record.",
                )

            record_ttl = record.get("ttl")

            if record_ttl is not None and record_ttl < MIN_DNS_TTL:
                raise ConfigurationError(
                    message=f"DNS record '{record_name}' ttl is less than {MIN_DNS_TTL} seconds.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint=f"Set the DNS record ttl to at least {MIN_DNS_TTL} seconds.",
                )

    def validate(self) -> None:

        self.validate_prerequisites()

        self.validate_platform_config()

        for domain in self.domains:
            self.validate_domain_config(domain)
