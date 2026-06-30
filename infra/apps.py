import pulumi
import pulumi_kubernetes as k8s

from app_naming import get_domain_application_namespace
from constants import ARGOCD_API_VERSION, ARGOCD_APPLICATION_KIND, ARGOCD_NAMESPACE


def create_domain_application_argocd_applications(settings, kubernetes_provider, domain_application_namespaces: dict) -> dict[str, k8s.apiextensions.CustomResource]:

    applications = {}

    for domain in settings.domains:

        domain_name = domain["name"]

        for domain_application in domain.get("applications", []):

            namespace_name = get_domain_application_namespace(
                settings=settings,
                application=domain_application,
                domain_name=domain_name,
            )

            resource_name = f"{domain_application}-{settings.domain_to_slug(domain_name)}"

            applications[resource_name] = k8s.apiextensions.CustomResource(
                resource_name,
                api_version=ARGOCD_API_VERSION,
                kind=ARGOCD_APPLICATION_KIND,
                metadata={
                    "name": resource_name,
                    "namespace": ARGOCD_NAMESPACE,
                },
                spec={
                    "project": "default",
                    "source": {
                        "repoURL": settings.repository_url,
                        "targetRevision": "main",
                        "path": f"apps/{domain_application}",
                    },
                    "destination": {
                        "server": "https://kubernetes.default.svc",
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
                        domain_application_namespaces[namespace_name],
                    ],
                ),
            )

    return applications