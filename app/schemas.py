# schemas.py - RevIA API
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    """Champs en snake_case côté Python, en camelCase dans le JSON."""
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Question(CamelModel):
    question: str = Field(min_length=1)
    propositions: list[str] = Field(min_length=2, max_length=6)
    index_bonne_reponse: int = Field(ge=0)
    explication: str = Field(min_length=1)
    theme: str = Field(min_length=1)

    @model_validator(mode="after")
    def index_dans_les_bornes(self):
        if self.index_bonne_reponse >= len(self.propositions):
            raise ValueError("indexBonneReponse hors des propositions")
        return self


class QCMResponse(CamelModel):
    qcm: list[Question] = Field(min_length=1)


class ErrorResponse(CamelModel):
    code: str
    message: str