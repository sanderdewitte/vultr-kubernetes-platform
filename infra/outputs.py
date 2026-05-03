import pulumi

def export_outputs(cluster):

    pulumi.export("cluster_id", cluster.id)
    pulumi.export("cluster_endpoint", cluster.endpoint)
    pulumi.export("kubeconfig", pulumi.Output.secret(cluster.kube_config))