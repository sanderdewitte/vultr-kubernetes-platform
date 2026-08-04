ALLOWED_APPLICATION_KEYS = {
    "namespace",
    "database",
    "chart",
    "default_host_prefix",
    "secret_requirements",
    "helm_parameter_paths",
}

ALLOWED_DATABASE_KEYS = {
    "enabled",
    "connection_url_secret",
}

ALLOWED_CHART_KEYS = {
    "repository_url",
    "version",
}

ALLOWED_HELM_PARAMETER_PATH_KEYS = {
    "database_name",
    "database_user",
    "database_connection_url_secret",
    "ingress_host",
    "ingress_tls_secret",
    "ingress_tls_host",
}

EXPECTED_HELM_PARAMETER_PATH_INDEX_COUNTS = {
    "database_name": 0,
    "database_user": 0,
    "database_connection_url_secret": 0,
    "ingress_host": 1,
    "ingress_tls_secret": 1,
    "ingress_tls_host": 2,
}

DATABASE_IDENTIFIER_HELM_PARAMETER_PATH_KEYS = {
    "database_name",
    "database_user",
}

DATABASE_CONNECTION_URL_HELM_PARAMETER_PATH_KEY = (
    "database_connection_url_secret"
)

INGRESS_HELM_PARAMETER_PATH_KEYS = {
    "ingress_host",
    "ingress_tls_secret",
    "ingress_tls_host",
}