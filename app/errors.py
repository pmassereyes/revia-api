# errors.py - RevIA API
class ApiError(Exception):
    status_code = 500
    code = "internal_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class InvalidTokenError(ApiError):
    status_code = 401
    code = "invalid_token"


class PdfTooLargeError(ApiError):
    status_code = 413
    code = "pdf_too_large"


class QuotaExceededError(ApiError):
    status_code = 429
    code = "quota_exceeded"


class GenerationFailedError(ApiError):
    status_code = 502
    code = "generation_failed"

class InvalidPdfError(ApiError):
    status_code = 400
    code = "invalid_pdf"

class RateLimitError(ApiError):
    status_code = 429
    code = "rate_limited"