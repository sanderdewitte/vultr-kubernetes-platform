import pulumi
import pulumi_kubernetes as k8s


CERT_MANAGER_NAMESPACE = "cert-manager"
PLATFORM_DATABASE_NAMESPACE = "platform-database"


def get_domain_application_namespace(settings, application, domain_name) -> str:

    domain_slug = settings.domain_to_slug(domain_name)

    return f"{application}-{domain_slug}"

def create_kubernetes_secrets(settings, kubernetes_provider) -> dict:

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

    domain_application_namespaces = {}
    domain_application_secrets = {}

    for domain in settings.domains:

        domain_name = domain["name"]

        for domain_application in domain.get("applications", []):

            application_config = settings.supported_applications[domain_application]

            namespace = None
            namespace_name = get_domain_application_namespace(
                settings=settings,
                application=domain_application,
                domain_name=domain_name,
            )

            if application_config.get("namespace", False):

                namespace = k8s.core.v1.Namespace(
                    namespace_name,
                    metadata={
                        "name": namespace_name,
                    },
                    opts=pulumi.ResourceOptions(
                        provider=kubernetes_provider,
                    ),
                )

                domain_application_namespaces[namespace_name] = namespace

            for secret_requirement in application_config.get("secret_requirements", []):

                secret_key = settings.secret_to_slug(secret_requirement)
                secret_name = (
                    f"{domain_application}-"
                    f"{settings.secret_to_slug(secret_requirement)}"
                )
                resource_name = (
                    f"{domain_application}-"
                    f"{settings.domain_to_slug(domain_name)}-"
                    f"{settings.secret_to_slug(secret_requirement)}"
                )

                domain_application_secrets[resource_name] = (
                    k8s.core.v1.Secret(
                        resource_name,
                        metadata={
                            "name": secret_name,
                            "namespace": namespace_name,
                        },
                        string_data={
                            secret_key: pulumi.Output.secret(
                                settings.get_domain_secret(
                                    application=domain_application,
                                    domain_name=domain_name,
                                    secret_name=secret_requirement,
                                )
                            ),
                        },
                        type="Opaque",
                        opts=pulumi.ResourceOptions(
                            provider=kubernetes_provider,
                            protect=True,
                            depends_on=[namespace],
                        ),
                    )
                )

    return {
        "vultr_credentials": vultr_credentials,
        "postgresql_superuser": postgresql_superuser,
        "postgresql_app": postgresql_app,
        "domain_application_namespaces": domain_application_namespaces,
        "domain_application_secrets": domain_application_secrets,
    }