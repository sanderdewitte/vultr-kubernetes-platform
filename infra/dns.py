import pulumi
import ediri_vultr as vultr


def get_resource_prefix(settings, domain_name) -> str:
    """
    Keep existing Pulumi resource names for the primary/imported domain.
    Use domain-based names for additional domains.
    """
    if domain_name == settings.primary_domain_name:
        return "platform"

    return settings.domain_to_slug(domain_name)

def create_dns_records(settings, platform_ip, vultr_provider) -> dict[str, vultr.DnsRecord]:
    """
    Create DNS records for the Kubernetes platform entry point.

    The apex A record points the domain to the VKE worker node public IP.
    The wildcard CNAME makes application hostnames resolve through the apex.

    TTL precedence:
    - record ttl if set
    - domain ttl if set
    - global dns_ttl
    """

    records = {}

    for domain in settings.domains:
        domain_name = domain["name"]
        domain_ttl = domain.get("ttl", settings.dns_ttl)
        resource_prefix = get_resource_prefix(settings, domain_name)

        if domain.get("apex", True):
            resource_name = f"{resource_prefix}-apex-a"

            records[resource_name] = vultr.DnsRecord(
                resource_name,
                domain=domain_name,
                name="",
                type="A",
                data=platform_ip,
                ttl=domain_ttl,
                opts=pulumi.ResourceOptions(
                    provider=vultr_provider,
                    protect=True,
                ),
            )

        if domain.get("wildcard", False):
            resource_name = f"{resource_prefix}-wildcard-cname"

            records[resource_name] = vultr.DnsRecord(
                resource_name,
                domain=domain_name,
                name="*",
                type="CNAME",
                data=domain_name,
                priority=-1,
                ttl=domain_ttl,
                opts=pulumi.ResourceOptions(
                    provider=vultr_provider,
                    protect=True,
                ),
            )

        for record in domain.get("records", []):
            record_name = record["name"]
            record_type = record["type"]
            record_data = record["data"]
            record_ttl = record.get("ttl", domain_ttl)

            resource_name = (
                f"{resource_prefix}-{record_name}-{record_type}".lower()
                .replace("*", "wildcard")
                .replace("@", "apex")
            )

            records[resource_name] = vultr.DnsRecord(
                resource_name,
                domain=domain_name,
                name=record_name,
                type=record_type,
                data=record_data,
                priority=record.get("priority", -1),
                ttl=record_ttl,
                opts=pulumi.ResourceOptions(
                    provider=vultr_provider,
                    protect=True,
                ),
            )

    return records