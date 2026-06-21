import pulumi

def export_outputs(cluster, platform_ip, dns_records) -> None:

    pulumi.export("cluster_id", cluster.id)
    pulumi.export("cluster_endpoint", cluster.endpoint)
    pulumi.export("kubeconfig", pulumi.Output.secret(cluster.kube_config))

    pulumi.export("platform_ip", platform_ip)

    dns_record_ids = {name: record.id for name, record in dns_records.items()}
    pulumi.export("dns_record_ids", dns_record_ids)