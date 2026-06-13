import os
from pathlib import Path
from dotenv import load_dotenv

import pulumi


MIN_DNS_TTL = 60


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

    def validate(self):

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

        if not self.vultr_api_key:
            raise ValueError(
                "VULTR_API_KEY is not set. "
                "Create infra/secrets.local.env or set the environment variable."
            )

        if not self.postgresql_superuser_password:
            raise ValueError(
                "POSTGRESQL_SUPERUSER_PASSWORD is not set. "
                "Create infra/secrets.local.env or set the environment variable."
            )
        
        if not self.postgresql_app_password:
            raise ValueError(
                "POSTGRESQL_APP_PASSWORD is not set. "
                "Create infra/secrets.local.env or set the environment variable."
            )