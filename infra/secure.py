import pulumi
import pulumi_kubernetes as k8s


def create_kubernetes_secrets(settings, kubernetes_provider):
    vultr_credentials = k8s.core.v1.Secret(
        "cert-manager-vultr-credentials",
        metadata={
            "name": "vultr-credentials",
            "namespace": "cert-manager",
        },
        string_data={
            "apiKey": pulumi.Output.secret(settings.vultr_api_key),
        },
        type="Opaque",
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
            protect=True,
        ),
    )

    return {
        "vultr_credentials": vultr_credentials,
    }