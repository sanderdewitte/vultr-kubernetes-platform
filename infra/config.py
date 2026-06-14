import os
from pathlib import Path
from dotenv import load_dotenv

import pulumi


MIN_DNS_TTL = 60
DOMAIN_SECRET_REQUIREMENTS = {
    "authentik": [
        "postgresql_password",
        "secret_key",
    ],
}


class Settings:

    def __init__(self):

        secrets_file = Path(__file__).parent / "secrets.local.env"
        load_dotenv(dotenv_path=secrets_file, override=False)
        self.vultr_api_key = os.environ.get("VULTR_API_KEY")
        self.postgresql_superuser_password = os.environ.get("POSTGRESQL_SUPERUSER_PASSWORD")
        self.postgresql_app_password = os.environ.get("POSTGRESQL_APP_PASSWORD")

        config = pulumi.Config()
        self.region = config.get("region") or "ams"
        self.cluster_name = config.get("cluster_name") or "vke-prd-01"
        self.kubernetes_version = config.require("kubernetes_version")
        self.worker_node_plan = config.get("worker_node_plan") or "vc2-2c-4gb"
        self.worker_node_count = config.get_int("worker_node_count") or 1

        self.dns_ttl = config.get_int("dns_ttl") or 300
        self.domains = config.require_object("domains")
        self.primary_domain_name = self.domains[0].get("name") if self.domains else None

        self.validate()

    @staticmethod
    def domain_to_slug(domain_name):

        return domain_name.lower().replace(".", "-")

    @staticmethod
    def domain_to_identifier(domain_name):

        return domain_name.lower().replace(".", "_")

    def get_domain_secret_env_name(self, application, domain_name, secret_name):

        domain_identifier = self.domain_to_identifier(domain_name)

        env_name = (
            f"{application}_"
            f"{domain_identifier}_"
            f"{secret_name}"
        )

        return env_name.upper()

    def get_domain_secret(self, application, domain_name, secret_name):

        return os.environ.get(self.get_domain_secret_env_name(application, domain_name, secret_name))

    def validate(self):

        for env_name, value in [
            ("VULTR_API_KEY", self.vultr_api_key),
            ("POSTGRESQL_SUPERUSER_PASSWORD", self.postgresql_superuser_password),
            ("POSTGRESQL_APP_PASSWORD", self.postgresql_app_password),
        ]:
            if not value:
                raise ValueError(
                    f"{env_name} is not set. "
                    "Create infra/secrets.local.env or set the environment variable."
                )

        if self.worker_node_count != 1:
            raise ValueError(
                "This low-cost DNS setup expects exactly one VKE worker node. "
                f"Configured worker_node_count is {self.worker_node_count}."
            )

        if self.dns_ttl < MIN_DNS_TTL:
            raise ValueError(f"dns_ttl should be at least {MIN_DNS_TTL} seconds.")

        if not self.domains:
            raise ValueError("At least one domain must be configured.")

        if not self.primary_domain_name:
            raise ValueError("The first domain entry must have a name.")

        for domain in self.domains:
            domain_name = domain.get("name")

            if not domain_name:
                raise ValueError("Each domain entry must have a name.")

            if not isinstance(domain.get("apex", True), bool):
                raise ValueError(f"Domain {domain_name}: apex must be true or false.")

            if not isinstance(domain.get("wildcard", False), bool):
                raise ValueError(f"Domain {domain_name}: wildcard must be true or false.")

            domain_ttl = domain.get("ttl")
            if domain_ttl is not None and domain_ttl < MIN_DNS_TTL:
                raise ValueError(
                    f"Domain {domain_name}: ttl should be at least {MIN_DNS_TTL} seconds"
                )

            for record in domain.get("records", []):
                if not record.get("name"):
                    raise ValueError(f"Domain {domain_name}: each record must have a name.")

                if not record.get("type"):
                    raise ValueError(f"Domain {domain_name}: each record must have a type.")

                if not record.get("data"):
                    raise ValueError(f"Domain {domain_name}: each record must have data.")

                record_ttl = record.get("ttl")
                if record_ttl is not None and record_ttl < MIN_DNS_TTL:
                    raise ValueError(
                        f"Domain {domain_name}, record {record.get('name')}: "
                        f"ttl should be at least {MIN_DNS_TTL} seconds."
                    )

            for application, secret_names in DOMAIN_SECRET_REQUIREMENTS.items():
                for secret_name in secret_names:
                    env_name = self.get_domain_secret_env_name(
                        application=application,
                        domain_name=domain_name,
                        secret_name=secret_name,
                    )
                    if not os.environ.get(env_name):
                        raise ValueError(
                            f"{env_name} is not set. "
                            "Create infra/secrets.local.env or set the environment variable."
                        )