import pulumi
import pulumi_kubernetes as k8s

from app_naming import (
    get_domain_application_database_identifier,
    get_domain_application_namespace,
)
from constants import (
    ARGOCD_API_VERSION,
    ARGOCD_APPLICATION_FINALIZER,
    ARGOCD_APPLICATION_KIND,
    ARGOCD_NAMESPACE,
    HELM_PATH_INDEX_PLACEHOLDER,
)


def replace_helm_path_indices(parameter_path: str, indices: list[int],) -> str:

    resolved_path = parameter_path

    for index in indices:
        resolved_path = resolved_path.replace(HELM_PATH_INDEX_PLACEHOLDER, f"[{index}]", 1)

    return resolved_path

def create_argocd_applications(settings, kubernetes_provider, domain_application_namespaces) -> dict[str, k8s.apiextensions.CustomResource]:

    argocd_applications = {}

    for domain in settings.domains:

        domain_name = domain["name"]

        for domain_application, application_config in settings.domain_applications(domain_name).items():

            default_host_prefix = application_config["default_host_prefix"]
            application_hostname = f"{default_host_prefix}.{domain_name}"
            application_tls_secret_name = f"{settings.domain_to_slug(application_hostname)}-tls"

            ingress = {
                "hosts": [
                    application_hostname,
                ],
                "tls": [
                    {
                        "secret_name": application_tls_secret_name,
                        "hosts": [
                            application_hostname,
                        ],
                    },
                ],
            }

            helm_parameter_paths = application_config.get("helm_parameter_paths", {})
            helm_parameters = []

            database_config = application_config.get("database", {})

            if database_config.get("enabled", False):

                database_identifier = (
                    get_domain_application_database_identifier(
                        settings=settings,
                        application=domain_application,
                        domain_name=domain_name,
                    )
                )

                if "database_name" in helm_parameter_paths:
                    helm_parameters.append(
                        {
                            "name": helm_parameter_paths["database_name"],
                            "value": database_identifier,
                        }
                    )

                if "database_user" in helm_parameter_paths:
                    helm_parameters.append(
                        {
                            "name": helm_parameter_paths["database_user"],
                            "value": database_identifier,
                        }
                    )

            if "ingress_host" in helm_parameter_paths:

                for host_index, host in enumerate(ingress["hosts"]):
                    helm_parameters.append(
                        {
                            "name": replace_helm_path_indices(helm_parameter_paths["ingress_host"], [host_index]),
                            "value": host,
                        }
                    )

            if "ingress_tls_secret" in helm_parameter_paths:

                for tls_index, tls in enumerate(ingress["tls"]):
                    helm_parameters.append(
                        {
                            "name": replace_helm_path_indices(helm_parameter_paths["ingress_tls_secret"], [tls_index]),
                            "value": tls["secret_name"],
                        }
                    )

                    for host_index, host in enumerate(tls["hosts"]):
                        helm_parameters.append(
                            {
                                "name": replace_helm_path_indices(helm_parameter_paths["ingress_tls_host"], [tls_index, host_index]),
                                "value": host,
                            }
                        )

            application_chart = application_config["chart"]

            namespace_name = get_domain_application_namespace(
                settings=settings,
                application=domain_application,
                domain_name=domain_name,
            )

            resource_name = namespace_name

            argocd_applications[resource_name] = (
                k8s.apiextensions.CustomResource(
                    resource_name,
                    api_version=ARGOCD_API_VERSION,
                    kind=ARGOCD_APPLICATION_KIND,
                    metadata={
                        "name": resource_name,
                        "namespace": ARGOCD_NAMESPACE,
                        "finalizers": [
                            ARGOCD_APPLICATION_FINALIZER,
                        ],
                    },
                    spec={
                        "project": "default",
                        "sources": [
                            {
                                "repoURL": (
                                    application_chart["repository_url"]
                                ),
                                "chart": domain_application,
                                "targetRevision": (
                                    application_chart["version"]
                                ),
                                "helm": {
                                    "valueFiles": [
                                        "$values/"
                                        f"apps/{domain_application}"
                                        "/values.yaml",
                                    ],
                                    "parameters": (
                                        helm_parameters
                                    ),
                                },
                            },
                            {
                                "repoURL": (
                                    settings.repository_url
                                ),
                                "targetRevision": "main",
                                "ref": "values",
                            },
                        ],
                        "destination": {
                            "server": (
                                "https://kubernetes.default.svc"
                            ),
                            "namespace": namespace_name,
                        },
                        "syncPolicy": {
                            "automated": {
                                "prune": True,
                                "selfHeal": True,
                            },
                            "syncOptions": [
                                "CreateNamespace=false",
                            ],
                        },
                    },
                    opts=pulumi.ResourceOptions(
                        provider=kubernetes_provider,
                        depends_on=[
                            domain_application_namespaces[
                                namespace_name
                            ],
                        ],
                    ),
                )
            )

    return argocd_applications