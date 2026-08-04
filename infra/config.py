import os
import yaml
import re
from pathlib import Path
from dotenv import load_dotenv

import pulumi

from constants import HELM_PATH_INDEX_PLACEHOLDER
from errors import (
    ConfigurationError,
    ConfigurationScope,
)
from schema import (
    ALLOWED_APPLICATION_KEYS,
    ALLOWED_DATABASE_KEYS,
    ALLOWED_CHART_KEYS,
    ALLOWED_HELM_PARAMETER_PATH_KEYS,
    EXPECTED_HELM_PARAMETER_PATH_INDEX_COUNTS,
    DATABASE_IDENTIFIER_HELM_PARAMETER_PATH_KEYS,
    DATABASE_CONNECTION_URL_HELM_PARAMETER_PATH_KEY,
    INGRESS_HELM_PARAMETER_PATH_KEYS,
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

        config = pulumi.Config()

        self.repository_url = config.require("repository_url")
        self.region = config.get("region") or "ams"
        self.cluster_name = config.get("cluster_name") or "vke-prd-01"
        self.kubernetes_version = config.require("kubernetes_version")
        self.worker_node_plan = config.get("worker_node_plan") or "vc2-2c-4gb"
        self.worker_node_count = config.get_int("worker_node_count") or 1
        self.dns_ttl = config.get_int("dns_ttl") or 300
        self.domains = config.require_object("domains")
        self.primary_domain_name = self.domains[0].get("name") if self.domains else None

        self.application_catalog = load_application_catalog()

        self.validate()

    @staticmethod
    def identifier_to_slug(identifier: str) -> str:

        return identifier.lower().replace("_", "-")

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

        domain = next(d for d in self.domains if d["name"] == domain_name)

        return {application: self.application_catalog[application] for application in domain.get("applications", [])}

    def validate_prerequisites(self) -> None:

        for env_name, value in [
            ("VULTR_API_KEY", self.vultr_api_key),
            ("POSTGRESQL_SUPERUSER_PASSWORD", self.postgresql_superuser_password),
            ("POSTGRESQL_APP_PASSWORD", self.postgresql_app_password),
        ]:
            if not value:
                raise ConfigurationError(
                    message = f"{env_name} is not set.",
                    hint = f"Create {SECRETS_FILE.name} or set the environment variable.",
                )

        if self.worker_node_count != 1:
            raise ConfigurationError(
                message = f"Configured worker_node_count is {self.worker_node_count}.",
                hint = "This low-cost DNS setup expects exactly one VKE worker node.",
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

        domain_applications = domain.get("applications", [])

        if not isinstance(domain_applications, list):
            raise ConfigurationError(
                message="applications is not a list.",
                scope=ConfigurationScope.DOMAIN,
                name=domain_name,
                hint="Define applications as a YAML list or omit it when no applications are required.",
            )

        for domain_application in domain_applications:

            if domain_application not in self.application_catalog:
                raise ConfigurationError(
                    message=f"Application '{domain_application}' is not present in the application catalog.",
                    scope=ConfigurationScope.DOMAIN,
                    name=domain_name,
                    hint=f"Add '{domain_application}' to {APPLICATION_CATALOG_FILE.name} or remove it from this domain's applications list.",
                )

            application_config = self.application_catalog[domain_application]

            self.validate_application_config(application_name=domain_application, application_config=application_config, domain_name=domain_name)

        self.validate_domain_dns_config(domain=domain, domain_name=domain_name)

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

        chart_config = application_config["chart"]

        if not isinstance(chart_config, dict):
            raise ConfigurationError(
                message="chart is not a dictionary.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Define chart as a YAML mapping containing repository_url and version.",
            )

        self.validate_allowed_keys("chart", chart_config, ALLOWED_CHART_KEYS, application_name)

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

        database_connection_url_secret_path_configured = "database_connection_url_secret" in helm_parameter_paths

        if connection_url_secret_enabled:

            if not database_connection_url_secret_path_configured:
                raise ConfigurationError(
                    message="database.connection_url_secret is enabled, but its Helm parameter path is not configured.",
                    scope=ConfigurationScope.APPLICATION,
                    name=application_name,
                    hint="Add helm_parameter_paths.database_connection_url_secret.",
                )

        elif database_connection_url_secret_path_configured:

            raise ConfigurationError(
                message="helm_parameter_paths.database_connection_url_secret is configured while database.connection_url_secret is disabled.",
                scope=ConfigurationScope.APPLICATION,
                name=application_name,
                hint="Enable database.connection_url_secret or remove helm_parameter_paths.database_connection_url_secret.",
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
