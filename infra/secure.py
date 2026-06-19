import pulumi
import pulumi_kubernetes as k8s


CERT_MANAGER_NAMESPACE = "cert-manager"
PLATFORM_DATABASE_NAMESPACE = "platform-database"


def get_domain_application_namespace(settings, application: str, domain_name: str) -> str:

    domain_slug = settings.domain_to_slug(domain_name)

    return f"{application}-{domain_slug}"

def get_domain_application_database_identifier(settings, application: str, domain_name: str) -> str:

    domain_identifier = settings.domain_to_identifier(domain_name)

    return f"{application}_{domain_identifier}"

def create_domain_application_database_secret(settings, kubernetes_provider, domain_application: str, domain_name: str) -> tuple[str, k8s.core.v1.Secret]:

    database_identifier = get_domain_application_database_identifier(
        settings=settings,
        application=domain_application,
        domain_name=domain_name,
    )
    database_secret_name = (
        f"{settings.secret_to_slug(database_identifier)}-postgresql"
    )

    secret = k8s.core.v1.Secret(
        database_secret_name,
        metadata={
            "name": database_secret_name,
            "namespace": PLATFORM_DATABASE_NAMESPACE,
        },
        string_data={
            "username": database_identifier,
            "password": pulumi.Output.secret(
                settings.get_domain_secret(
                    application=domain_application,
                    domain_name=domain_name,
                    secret_name="postgresql_password",
                )
            ),
        },
        type="kubernetes.io/basic-auth",
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
            protect=True,
        ),
    )

    return database_secret_name, secret

def create_domain_application_namespace(kubernetes_provider, namespace_name: str) -> k8s.core.v1.Namespace:

    return k8s.core.v1.Namespace(
        namespace_name,
        metadata={
            "name": namespace_name,
        },
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
        ),
    )

def create_domain_application_secret(settings, kubernetes_provider, domain_application: str, domain_name: str, namespace_name: str, secret_requirement: str, namespace) -> tuple[str, k8s.core.v1.Secret]:

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

    secret = k8s.core.v1.Secret(
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

    return resource_name, secret

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
    domain_application_database_secrets = {}

    for domain in settings.domains:

        domain_name = domain["name"]

        for domain_application in domain.get("applications", []):

            application_config = settings.supported_applications[domain_application]

            if application_config.get("database", False):

                resource_name, database_secret = create_domain_application_database_secret(
                    settings=settings,
                    kubernetes_provider=kubernetes_provider,
                    domain_application=domain_application,
                    domain_name=domain_name,
                )

                domain_application_database_secrets[resource_name] = database_secret

            namespace = None
            namespace_name = get_domain_application_namespace(
                settings=settings,
                application=domain_application,
                domain_name=domain_name,
            )

            if application_config.get("namespace", False):

                namespace = create_domain_application_namespace(
                    kubernetes_provider=kubernetes_provider,
                    namespace_name=namespace_name,
                )

                domain_application_namespaces[namespace_name] = namespace

            if namespace:

                for secret_requirement in application_config.get("secret_requirements", []):

                    resource_name, secret = create_domain_application_secret(
                        settings=settings,
                        kubernetes_provider=kubernetes_provider,
                        domain_application=domain_application,
                        domain_name=domain_name,
                        namespace_name=namespace_name,
                        secret_requirement=secret_requirement,
                        namespace=namespace,
                    )

                    domain_application_secrets[resource_name] = secret

    return {
        "vultr_credentials": vultr_credentials,
        "postgresql_superuser": postgresql_superuser,
        "postgresql_app": postgresql_app,
        "domain_application_namespaces": domain_application_namespaces,
        "domain_application_secrets": domain_application_secrets,
        "domain_application_database_secrets": domain_application_database_secrets,
    }