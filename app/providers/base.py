# base.py - RevIA API
from typing import Protocol

from app.schemas import QCMResponse


class QCMProvider(Protocol):
    async def generate_qcm(self, pdf: bytes, nb_questions: int) -> QCMResponse: ...