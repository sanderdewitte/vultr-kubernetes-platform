import os
import yaml
from pathlib import Path
from dotenv import load_dotenv

import pulumi


INFRA_DIR = Path(__file__).parent
BASE_DIR = INFRA_DIR.parent

SECRETS_FILE = INFRA_DIR / "secrets.local.env"
APPLICATION_CATALOG_FILE = BASE_DIR / "apps" / "apps.yaml"

ALLOWED_DATABASE_KEYS = {"enabled", "connection_url_secret"}
ALLOWED_CHART_KEYS = {"repository_url", "version"}

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
                raise ValueError(
                    f"{env_name} is not set. "
                    f"Create {SECRETS_FILE.name} or set the environment variable."
                )

        if self.worker_node_count != 1:
            raise ValueError(
                "This low-cost DNS setup expects exactly one VKE worker node. "
                f"Configured worker_node_count is {self.worker_node_count}."
            )

    def validate_platform_config(self) -> None:

        if self.dns_ttl < MIN_DNS_TTL:
            raise ValueError(f"dns_ttl should be at least {MIN_DNS_TTL} seconds.")

        if not self.domains:
            raise ValueError("At least one domain must be configured.")

        if not self.primary_domain_name:
            raise ValueError("The first domain entry must have a name.")

        if not isinstance(self.application_catalog, dict):
            raise ValueError(
                f"{APPLICATION_CATALOG_FILE.name} "
                "must contain a dictionary "
                "of supported applications."
            )

    def validate_domain_config(self, domain: dict) -> None:

        domain_name = domain.get("name")

        if not domain_name:
            raise ValueError("Each domain entry must have a name.")

        if not isinstance(domain.get("apex", True), bool):
            raise ValueError(f"Domain {domain_name}: apex must be true or false.")

        if not isinstance(domain.get("wildcard", False), bool):
            raise ValueError(f"Domain {domain_name}: wildcard must be true or false.")

        domain_applications = domain.get("applications", [])

        if not isinstance(domain_applications, list):
            raise ValueError(f"Domain {domain_name}: applications must be a list.")

        for domain_application in domain_applications:

            if domain_application not in self.application_catalog:
                raise ValueError(f"Domain {domain_name}: unknown application '{domain_application}'.")

            application_config = self.application_catalog[domain_application]

            self.validate_application_config(application_name=domain_application, application_config=application_config, domain_name=domain_name)

        self.validate_domain_dns_config(domain=domain, domain_name=domain_name)

    def validate_allowed_keys(self, section_name: str, configuration: dict, allowed_keys: set[str], application_name: str) -> None:

        unknown_keys = set(configuration) - allowed_keys

        if unknown_keys:
            raise ValueError(
                f"Application '{application_name}': "
                f"unknown key(s) in '{section_name}': "
                f"{', '.join(sorted(unknown_keys))}."
            )

    def validate_application_config(self, application_name: str, application_config: dict, domain_name: str) -> None:

        secret_requirements = application_config.get("secret_requirements", [])

        if secret_requirements and not application_config.get("namespace", False):
            raise ValueError(
                f"Application '{application_name}' defines "
                "secret_requirements but namespace is not enabled."
            )

        for secret_name in secret_requirements:

            env_name = self.get_domain_secret_env_name(
                application=application_name,
                domain_name=domain_name,
                secret_name=secret_name,
            )

            if not os.environ.get(env_name):
                raise ValueError(
                    f"{env_name} is not set. "
                    f"Create {SECRETS_FILE.name} or set the environment variable."
                )

        database_config = application_config.get("database", {})

        if not isinstance(database_config, dict):
            raise ValueError(
                f"Application '{application_name}': "
                "database must be a dictionary."
            )

        self.validate_allowed_keys("database", database_config, ALLOWED_DATABASE_KEYS, application_name)

        database_enabled = database_config.get("enabled", False)

        if not isinstance(database_enabled, bool):
            raise ValueError(
                f"Application '{application_name}': "
                "database.enabled must be true or false."
            )

        connection_url_secret_enabled = database_config.get("connection_url_secret", False)

        if not isinstance(connection_url_secret_enabled, bool):
            raise ValueError(
                f"Application '{application_name}': "
                "database.connection_url_secret "
                "must be true or false."
            )

        if connection_url_secret_enabled and not database_enabled:
            raise ValueError(
                f"Application '{application_name}': "
                "database.connection_url_secret "
                "requires database.enabled."
            )

        if connection_url_secret_enabled and not application_config.get("namespace", False):
            raise ValueError(
                f"Application '{application_name}': "
                "database.connection_url_secret "
                "requires namespace to be enabled."
            )

        chart_config = application_config["chart"]

        if not isinstance(chart_config, dict):
            raise ValueError(
                f"Application '{application_name}': "
                "chart must be a dictionary."
            )

        self.validate_allowed_keys("chart", chart_config, ALLOWED_CHART_KEYS, application_name)

    def validate_domain_dns_config(self, domain: dict, domain_name: str) -> None:

        domain_ttl = domain.get("ttl")

        if domain_ttl is not None and domain_ttl < MIN_DNS_TTL:
            raise ValueError(
                f"Domain {domain_name}: ttl should be at least "
                f"{MIN_DNS_TTL} seconds."
            )

        for record in domain.get("records", []):

            record_name = record.get("name")

            if not record_name:
                raise ValueError(f"Domain {domain_name}: each record must have a name.")

            if not record.get("type"):
                raise ValueError(f"Domain {domain_name}: each record must have a type.")

            if not record.get("data"):
                raise ValueError(f"Domain {domain_name}: each record must have data.")

            record_ttl = record.get("ttl")

            if record_ttl is not None and record_ttl < MIN_DNS_TTL:
                raise ValueError(
                    f"Domain {domain_name}, record {record_name}: "
                    f"ttl should be at least {MIN_DNS_TTL} seconds."
                )

    def validate(self) -> None:

        self.validate_prerequisites()

        self.validate_platform_config()

        for domain in self.domains:
            self.validate_domain_config(domain)
