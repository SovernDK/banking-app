from enum import StrEnum


class BankErrorCode(StrEnum):
    ACCESS_DENIED = "access_denied"
    INVALID_CALLBACK = "invalid_callback"
    INVALID_STATE = "invalid_state"
    BANK_UNAVAILABLE = "bank_unavailable"
    SESSION_EXPIRED = "session_expired"
    NOT_CONFIGURED = "not_configured"

    @property
    def message(self) -> str:
        return _MESSAGES[self]


_MESSAGES = {
    BankErrorCode.ACCESS_DENIED: "The bank did not grant access. Try connecting again.",
    BankErrorCode.INVALID_CALLBACK: (
        "The bank returned an unexpected response. Try connecting again."
    ),
    BankErrorCode.INVALID_STATE: (
        "This bank connection link is no longer valid. Start a new connection."
    ),
    BankErrorCode.BANK_UNAVAILABLE: "The bank service is unavailable right now. Try again later.",
    BankErrorCode.SESSION_EXPIRED: (
        "Your bank connection has expired. Connect again to refresh it."
    ),
    BankErrorCode.NOT_CONFIGURED: (
        "Bank access is not configured. Set the Enable Banking credentials in .env."
    ),
}
