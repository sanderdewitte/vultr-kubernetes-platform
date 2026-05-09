import pulumi

class Settings:

    def __init__(self):

        config = pulumi.Config()

        self.region = config.get("region") or "ams"
        self.cluster_name = config.get("cluster_name") or "vke-prd-01"
        self.kubernetes_version = config.require("kubernetes_version")
        self.worker_node_plan = config.get("worker_node_plan") or "vc2-2c-4gb"
        self.worker_node_count = config.get_int("worker_node_count") or 1

        self.domain_name = config.require("domain_name")
        self.dns_ttl = config.get_int("dns_ttl") or 300

        self.validate()

    def validate(self):

        if self.worker_node_count != 1:
            raise ValueError(
                "This low-cost DNS setup expects exactly one VKE worker node. "
                f"Configured worker_node_count is {self.worker_node_count}."
            )

        if not self.domain_name:
            raise ValueError("domain_name must not be empty.")

        if self.dns_ttl < 60:
            raise ValueError("dns_ttl should be at least 60 seconds.")