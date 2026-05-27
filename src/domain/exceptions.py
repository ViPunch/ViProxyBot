class VPNBotError(Exception):
    pass


class ProtocolNotInstalledError(VPNBotError):
    pass


class PortInUseError(VPNBotError):
    pass


class ClientNotFoundError(VPNBotError):
    pass


class ClientAlreadyExistsError(VPNBotError):
    pass


class ConfigValidationError(VPNBotError):
    pass


class ServiceReloadError(VPNBotError):
    pass


class UnauthorizedError(VPNBotError):
    pass
