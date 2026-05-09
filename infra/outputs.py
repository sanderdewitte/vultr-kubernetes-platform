import pulumi

def export_outputs(cluster, platform_ip, dns_records):

    pulumi.export("cluster_id", cluster.id)
    pulumi.export("cluster_endpoint", cluster.endpoint)
    pulumi.export("kubeconfig", pulumi.Output.secret(cluster.kube_config))

    pulumi.export("platform_ip", platform_ip)
    pulumi.export("dns_apex_record_id", dns_records["apex_record"].id)
    pulumi.export("dns_wildcard_record_id", dns_records["wildcard_record"].id)