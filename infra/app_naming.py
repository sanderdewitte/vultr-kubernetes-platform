def get_domain_application_namespace(settings, application: str, domain_name: str) -> str:

    domain_slug = settings.domain_to_slug(domain_name)

    return f"{application}-{domain_slug}"


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

    database_identifier = get_domain_application_database_identifier(
        settings=settings,
        application=application,
        domain_name=domain_name,
    )

    return f"{settings.identifier_to_slug(database_identifier)}-postgresql"