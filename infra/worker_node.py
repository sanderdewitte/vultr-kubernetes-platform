import pulumi
import ediri_vultr as vultr

def get_first_worker_node_id(cluster):
    """
    Return the Vultr instance ID of the first worker node in the VKE node pool.
    This assumes a low-cost setup with exactly one worker node.
    """

    def extract_node_id(node_pool):
        nodes = node_pool.get("nodes", [])

        if not nodes:
            raise ValueError("VKE node pool does not contain any nodes.")

        if len(nodes) > 1:
            raise ValueError(
                "Expected exactly one VKE worker node, but found "
                f"{len(nodes)} nodes. This setup assumes a single public entry node."
            )

        node_id = nodes[0].get("id")

        if not node_id:
            raise ValueError("VKE worker node does not have a Vultr instance ID.")

        return node_id

    return cluster.node_pools.apply(extract_node_id)


def get_first_worker_public_ip(cluster, vultr_provider):
    """
    Look up the first VKE worker node as a Vultr instance and return its public IP.
    """

    worker_node_id = get_first_worker_node_id(cluster)

    worker_instance = vultr.Instance.get(
        "vke-worker-instance",
        id=worker_node_id,
        opts=pulumi.ResourceOptions(provider=vultr_provider),
    )

    return worker_instance.main_ip
