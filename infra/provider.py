import pulumi
import ediri_vultr as vultr


def create_vultr_provider(settings):
    return vultr.Provider(
        "vultr-provider",
        api_key=pulumi.Output.secret(settings.vultr_api_key),
    )