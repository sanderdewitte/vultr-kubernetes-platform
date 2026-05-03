import pulumi

class Settings:

    def __init__(self):

        config = pulumi.Config()

        self.region = config.get("region") or "ams"
        self.cluster_name = config.get("cluster_name") or "vke-prd-01"
        self.kubernetes_version = config.require("kubernetes_version")
        self.worker_node_plan = config.get("worker_node_plan") or "vc2-2c-4gb"
        self.worker_node_count = config.get_int("worker_node_count") or 1