import asyncio
import json
from pathlib import Path

from app.cache import CachedProvider
from app.schemas import QCMResponse

FIXTURE = Path(__file__).parent / "fixtures" / "reponse_exemple.json"
PDF = b"%PDF-1.4 contenu A"


class CountingProvider:
    def __init__(self) -> None:
        self.calls = 0

    async def generate_qcm(self, pdf: bytes, nb_questions: int) -> QCMResponse:
        self.calls += 1
        return QCMResponse.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def test_meme_pdf_un_seul_appel(tmp_path):
    inner = CountingProvider()
    cached = CachedProvider(inner, tmp_path)
    asyncio.run(cached.generate_qcm(PDF, 5))
    asyncio.run(cached.generate_qcm(PDF, 5))
    assert inner.calls == 1


def test_parametres_differents_deux_appels(tmp_path):
    inner = CountingProvider()
    cached = CachedProvider(inner, tmp_path)
    asyncio.run(cached.generate_qcm(PDF, 5))
    asyncio.run(cached.generate_qcm(PDF, 10))
    asyncio.run(cached.generate_qcm(b"%PDF-1.4 contenu B", 5))
    assert inner.calls == 3


def test_cache_corrompu_regenere(tmp_path):
    inner = CountingProvider()
    cached = CachedProvider(inner, tmp_path)
    asyncio.run(cached.generate_qcm(PDF, 5))
    for f in tmp_path.glob("*.json"):
        f.write_text("pas du json")
    asyncio.run(cached.generate_qcm(PDF, 5))
    assert inner.calls == 2