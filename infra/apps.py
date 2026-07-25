import pulumi
import pulumi_kubernetes as k8s

from app_naming import get_domain_application_database_identifier, get_domain_application_namespace
from constants import ARGOCD_API_VERSION, ARGOCD_APPLICATION_KIND, ARGOCD_NAMESPACE
from constants import ARGOCD_API_VERSION, ARGOCD_APPLICATION_FINALIZER, ARGOCD_APPLICATION_KIND, ARGOCD_NAMESPACE


def create_argocd_applications(settings, kubernetes_provider, domain_application_namespaces) -> dict[str, k8s.apiextensions.CustomResource]:

    argocd_applications = {}

    for domain in settings.domains:

        domain_name = domain["name"]

        for domain_application, application_config in settings.domain_applications(domain_name).items():

            application_hostname = f"{application_config['host_prefix']}.{domain_name}"
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

            helm_parameters = []

            if application_config.get("database", False):

                database_identifier = (
                    get_domain_application_database_identifier(
                        settings=settings,
                        application=domain_application,
                        domain_name=domain_name,
                    )
                )

                helm_parameters.extend(
                    [
                        {
                            "name": (
                                f"{domain_application}.postgresql.name"
                            ),
                            "value": database_identifier,
                        },
                        {
                            "name": (
                                f"{domain_application}.postgresql.user"
                            ),
                            "value": database_identifier,
                        },
                    ]
                )

            for host_index, host in enumerate(ingress["hosts"]):
                helm_parameters.append(
                    {
                        "name": (
                            f"server.ingress.hosts[{host_index}]"
                        ),
                        "value": host,
                    }
                )

            for tls_index, tls in enumerate(ingress["tls"]):
                helm_parameters.append(
                    {
                        "name": (
                            f"server.ingress.tls[{tls_index}]"
                            ".secretName"
                        ),
                        "value": tls["secret_name"],
                    }
                )

                for host_index, host in enumerate(tls["hosts"]):
                    helm_parameters.append(
                        {
                            "name": (
                                f"server.ingress.tls[{tls_index}]"
                                f".hosts[{host_index}]"
                            ),
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