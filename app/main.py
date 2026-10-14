# main.py - RevIA API
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors import ApiError, InvalidRequestError
from app.routers import health, qcm
from app.schemas import ErrorResponse

app = FastAPI(title="RevIA API", version="0.1.0")
app.include_router(health.router)
app.include_router(qcm.router)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    body = ErrorResponse(code=exc.code, message=exc.message)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(by_alias=True))


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    champs = sorted({str(e["loc"][-1]) for e in exc.errors()})
    message = f"Requête invalide (champs en cause : {', '.join(champs)})."
    return await api_error_handler(request, InvalidRequestError(message))


# Dernier recours : la trace reste dans les journaux du serveur, le client reçoit {code, message}
@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    return await api_error_handler(request, ApiError("Erreur interne du serveur."))
