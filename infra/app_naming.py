from constants import URL_IDENTIFIER


def get_domain_application_namespace(settings, application: str, domain_name: str) -> str:

    application_slug = settings.identifier_to_slug(application)
    domain_slug = settings.domain_to_slug(domain_name)

    return f"{application_slug}-{domain_slug}"


def get_domain_application_resource_name(settings, application: str, domain_name: str) -> str:

    return get_domain_application_namespace(
        settings=settings,
        application=application,
        domain_name=domain_name,
    )


def get_domain_application_database_identifier(settings, application: str, domain_name: str) -> str:

    domain_identifier = settings.domain_to_identifier(domain_name)

    return f"{application}_{domain_identifier}"


def get_domain_application_database_secret_name(settings, application: str, domain_name: str) -> str:

    application_database_identifier = (
        get_domain_application_database_identifier(
            settings=settings,
            application=application,
            domain_name=domain_name,
        )
    )

    application_database_identifier_slug = settings.identifier_to_slug(application_database_identifier)

    return f"{application_database_identifier_slug}-postgresql"


def get_application_database_url_secret_name(settings, application: str) -> str:

    application_slug = settings.identifier_to_slug(application)
    database_resource_suffix = f"postgresql-{URL_IDENTIFIER}"

    return f"{application_slug}-{database_resource_suffix}"