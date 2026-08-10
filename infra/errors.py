from enum import Enum


class ConfigurationScope(Enum):

    PLATFORM = "Platform"
    DOMAIN = "Domain"
    APPLICATION = "Application"


class ConfigurationError(ValueError):

    def __init__(self, message: str, *, scope: ConfigurationScope = ConfigurationScope.PLATFORM, name: str | None = None, hint: str | None = None) -> None:

        error_message = f"\n{scope.value}"

        if name:
            error_message += f" '{name}'"

        error_message += f": {message}"

        if hint:
            error_message += f"\nHint: {hint}"

        super().__init__(error_message)
