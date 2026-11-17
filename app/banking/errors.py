from enum import StrEnum


class BankErrorCode(StrEnum):
    ACCESS_DENIED = "access_denied"
    INVALID_CALLBACK = "invalid_callback"
    INVALID_STATE = "invalid_state"
    BANK_UNAVAILABLE = "bank_unavailable"
    SESSION_EXPIRED = "session_expired"
    NOT_CONFIGURED = "not_configured"
