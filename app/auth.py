# auth.py - RevIA API
import secrets

from fastapi import Header

from app.config import settings
from app.errors import InvalidTokenError


def verify_token(x_api_token: str = Header(default="")) -> None:
    expected = settings.api_token
    if not expected or not secrets.compare_digest(x_api_token, expected):
        raise InvalidTokenError("Jeton invalide ou manquant.")