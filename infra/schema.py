ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_KEYS = {
    "host_prefix",
    "authentication",
}

ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_AUTH_KEYS = {
    "oidc",
}

ALLOWED_APPLICATION_DOMAIN_DEPLOYMENT_AUTH_OIDC_KEYS = {
    "identity_provider",
}

ALLOWED_APPLICATION_KEYS = {
    "namespace",
    "database",
    "authentication",
    "chart",
    "default_host_prefix",
    "secret_requirements",
    "helm_parameter_paths",
}

ALLOWED_DATABASE_KEYS = {
    "enabled",
    "connection_url_secret",
}

ALLOWED_AUTH_KEYS = {
    "oidc",
}

ALLOWED_AUTH_OIDC_KEYS = {
    "secret_requirements",
    "helm_parameter_paths",
}

ALLOWED_CHART_KEYS = {
    "repository_url",
    "version",
}

DATABASE_IDENTIFIER_HELM_PARAMETER_PATH_KEYS = {
    "database_name",
    "database_user",
}

INGRESS_HELM_PARAMETER_PATH_KEYS = {
    "ingress_host",
    "ingress_tls_secret",
    "ingress_tls_host",
}

OIDC_HELM_PARAMETER_PATH_KEYS = {
    "providers",
    "issuer",
    "client_name",
    "scope",
    "groups_attribute",
    "logout_redirect_url",
}

REQUIRED_OIDC_SECRET_REQUIREMENTS = {
    "client_id",
    "client_secret",
}

SINGLE_VALUE_HELM_PARAMETER_PATH_KEYS = (
    DATABASE_IDENTIFIER_HELM_PARAMETER_PATH_KEYS
    | OIDC_HELM_PARAMETER_PATH_KEYS
)

INDEXED_HELM_PARAMETER_PATH_KEYS = (
    INGRESS_HELM_PARAMETER_PATH_KEYS
)

ALLOWED_HELM_PARAMETER_PATH_KEYS = (
    SINGLE_VALUE_HELM_PARAMETER_PATH_KEYS
    | INDEXED_HELM_PARAMETER_PATH_KEYS
)

INDEXED_HELM_PARAMETER_PATH_INDEX_COUNTS = {
    "ingress_host": 1,
    "ingress_tls_secret": 1,
    "ingress_tls_host": 2,
}

EXPECTED_HELM_PARAMETER_PATH_INDEX_COUNTS = {
    **{key: 0 for key in SINGLE_VALUE_HELM_PARAMETER_PATH_KEYS},
    **INDEXED_HELM_PARAMETER_PATH_INDEX_COUNTS,
}