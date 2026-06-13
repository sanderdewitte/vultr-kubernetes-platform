import pulumi
import pulumi_kubernetes as k8s


CERT_MANAGER_NAMESPACE = "cert-manager"
PLATFORM_DATABASE_NAMESPACE = "platform-database"


def create_kubernetes_secrets(settings, kubernetes_provider):

    vultr_credentials = k8s.core.v1.Secret(
        "cert-manager-vultr-credentials",
        metadata={
            "name": "vultr-credentials",
            "namespace": CERT_MANAGER_NAMESPACE,
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

    postgresql_superuser = k8s.core.v1.Secret(
        "postgresql-superuser",
        metadata={
            "name": "postgresql-superuser",
            "namespace": PLATFORM_DATABASE_NAMESPACE,
        },
        string_data={
            "username": "postgres",
            "password": pulumi.Output.secret(settings.postgresql_superuser_password),
        },
        type="kubernetes.io/basic-auth",
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
            protect=True,
        ),
    )

    postgresql_app = k8s.core.v1.Secret(
        "postgresql-app",
        metadata={
            "name": "postgresql-app",
            "namespace": PLATFORM_DATABASE_NAMESPACE,
        },
        string_data={
            "username": "platform",
            "password": pulumi.Output.secret(settings.postgresql_app_password),
        },
        type="kubernetes.io/basic-auth",
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
            protect=True,
        ),
    )

    return {
        "vultr_credentials": vultr_credentials,
        "postgresql_superuser": postgresql_superuser,
        "postgresql_app": postgresql_app,
    }