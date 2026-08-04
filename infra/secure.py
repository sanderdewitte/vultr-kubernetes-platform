from urllib.parse import quote

import pulumi
import pulumi_kubernetes as k8s

from constants import (
    VULTR_CREDENTIALS_SECRET_KEY,
    CERT_MANAGER_NAMESPACE,
    PLATFORM_DATABASE_NAMESPACE,
    POSTGRESQL_CLUSTER_NAME,
    POSTGRESQL_SUPERUSER_SECRET_KEY,
    POSTGRESQL_APP_SECRET_KEY,
    DOMAIN_APPLICATION_NAMESPACES_KEY,
    URL_IDENTIFIER,
)
from app_naming import (
    get_domain_application_namespace,
    get_domain_application_database_identifier,
    get_domain_application_database_secret_name,
    get_application_database_url_secret_name,
)


def create_domain_application_database_secret(settings, kubernetes_provider, domain_application: str, domain_name: str) -> tuple[str, k8s.core.v1.Secret]:

    database_identifier = get_domain_application_database_identifier(
        settings=settings,
        application=domain_application,
        domain_name=domain_name,
    )

    database_secret_name = get_domain_application_database_secret_name(
        settings=settings,
        application=domain_application,
        domain_name=domain_name,
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


def create_domain_application_database_url_secret(settings, kubernetes_provider, domain_application: str, domain_name: str, namespace_name: str, namespace) -> tuple[str, k8s.core.v1.Secret]:

    database_resource_suffix = f"postgresql-{URL_IDENTIFIER}"
    database_secret_key = URL_IDENTIFIER
    postgresql_port = 5432

    database_url_secret_name = (
        get_application_database_url_secret_name(
            settings=settings,
            application=domain_application,
        )
    )

    resource_name = (
        f"{domain_application}-"
        f"{settings.domain_to_slug(domain_name)}-"
        f"{database_resource_suffix}"
    )

    database_password = settings.get_domain_secret(
        application=domain_application,
        domain_name=domain_name,
        secret_name="postgresql_password",
    )

    database_identifier = get_domain_application_database_identifier(
        settings=settings,
        application=domain_application,
        domain_name=domain_name,
    )

    database_url = pulumi.Output.secret(database_password).apply(
        lambda password: (
            f"postgresql://{database_identifier}:"
            f"{quote(password, safe='')}"
            f"@{POSTGRESQL_CLUSTER_NAME}-rw."
            f"{PLATFORM_DATABASE_NAMESPACE}.svc.cluster.local:"
            f"{postgresql_port}/"
            f"{database_identifier}"
        )
    )

    secret = k8s.core.v1.Secret(
        resource_name,
        metadata={
            "name": database_url_secret_name,
            "namespace": namespace_name,
        },
        string_data={
            database_secret_key: database_url,
        },
        type="Opaque",
        opts=pulumi.ResourceOptions(
            provider=kubernetes_provider,
            protect=True,
            depends_on=[namespace],
        ),
    )

    return resource_name, secret


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

    secret_key = settings.identifier_to_slug(secret_requirement)

    secret_name = (
        f"{domain_application}-"
        f"{settings.identifier_to_slug(secret_requirement)}"
    )

    resource_name = (
        f"{domain_application}-"
        f"{settings.domain_to_slug(domain_name)}-"
        f"{settings.identifier_to_slug(secret_requirement)}"
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

    vultr_credentials_secret_name = settings.identifier_to_slug(VULTR_CREDENTIALS_SECRET_KEY)
    vultr_credentials_resource_name = f"{CERT_MANAGER_NAMESPACE}-{vultr_credentials_secret_name}"
    vultr_credentials = k8s.core.v1.Secret(
        vultr_credentials_resource_name,
        metadata={
            "name": vultr_credentials_secret_name,
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

    postgresql_superuser_secret_name = settings.identifier_to_slug(POSTGRESQL_SUPERUSER_SECRET_KEY)
    postgresql_superuser = k8s.core.v1.Secret(
        postgresql_superuser_secret_name,
        metadata={
            "name": postgresql_superuser_secret_name,
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

    postgresql_app_secret_name = settings.identifier_to_slug(POSTGRESQL_APP_SECRET_KEY)
    postgresql_app = k8s.core.v1.Secret(
        postgresql_app_secret_name,
        metadata={
            "name": postgresql_app_secret_name,
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
    domain_application_database_url_secrets = {}

    for domain in settings.domains:

        domain_name = domain["name"]

        for domain_application, application_config in settings.domain_applications(domain_name).items():

            database_config = application_config.get("database", {})

            if database_config.get("enabled", False):

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

                if database_config.get("connection_url_secret", False):

                    resource_name, database_url_secret = (
                        create_domain_application_database_url_secret(
                            settings=settings,
                            kubernetes_provider=kubernetes_provider,
                            domain_application=domain_application,
                            domain_name=domain_name,
                            namespace_name=namespace_name,
                            namespace=namespace,
                        )
                    )

                    domain_application_database_url_secrets[resource_name] = database_url_secret

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
        VULTR_CREDENTIALS_SECRET_KEY: vultr_credentials,
        POSTGRESQL_SUPERUSER_SECRET_KEY: postgresql_superuser,
        POSTGRESQL_APP_SECRET_KEY: postgresql_app,
        DOMAIN_APPLICATION_NAMESPACES_KEY: domain_application_namespaces,
        "domain_application_secrets": domain_application_secrets,
        "domain_application_database_secrets": domain_application_database_secrets,
        "domain_application_database_url_secrets": domain_application_database_url_secrets,
    }