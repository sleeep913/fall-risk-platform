class EzvizConfigurationError(Exception):
    """Required server-side EZVIZ credentials are missing."""


class EzvizApiError(Exception):
    def __init__(
        self,
        message: str,
        *,
        platform_code: str | None = None,
        http_status: int | None = None,
        retryable: bool = False,
        token_invalid: bool = False,
    ) -> None:
        super().__init__(message)
        self.platform_code = platform_code
        self.http_status = http_status
        self.retryable = retryable
        self.token_invalid = token_invalid
