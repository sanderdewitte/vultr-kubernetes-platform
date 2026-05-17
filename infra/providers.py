import base64

import pulumi
import ediri_vultr as vultr
import pulumi_kubernetes as k8s


def decode_kubeconfig(kubeconfig):
    return base64.b64decode(kubeconfig).decode("utf-8")

def create_vultr_provider(settings):
    return vultr.Provider(
        "vultr-provider",
        api_key=pulumi.Output.secret(settings.vultr_api_key),
    )

def create_kubernetes_provider(cluster):
    return k8s.Provider(
        "vke-kubernetes-provider",
        kubeconfig=cluster.kube_config.apply(decode_kubeconfig),
    )
