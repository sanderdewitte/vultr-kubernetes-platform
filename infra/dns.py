import pulumi
import ediri_vultr as vultr

def create_dns_records(settings, platform_ip):
    """
    Create DNS records for the Kubernetes platform entry point.

    The apex A record points the domain to the VKE worker node public IP.
    The wildcard CNAME makes application hostnames resolve through the apex.
    """

    apex_record = vultr.DnsRecord(
        "platform-apex-a",
        domain=settings.domain_name,
        name="",
        type="A",
        data=platform_ip,
        ttl=settings.dns_ttl,
        opts=pulumi.ResourceOptions(protect=True),
    )

    wildcard_record = vultr.DnsRecord(
        "platform-wildcard-cname",
        domain=settings.domain_name,
        name="*",
        type="CNAME",
        data=settings.domain_name,
        priority=-1,
        ttl=settings.dns_ttl,
        opts=pulumi.ResourceOptions(protect=True),
    )

    return {
        "apex_record": apex_record,
        "wildcard_record": wildcard_record,
    }