# main.py - RevIA API
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import ApiError
from app.routers import health
from app.schemas import ErrorResponse

app = FastAPI(title="RevIA API", version="0.1.0")
app.include_router(health.router)


@app.exception_handler(ApiError)
async def api_error_handler(request: Request, exc: ApiError):
    body = ErrorResponse(code=exc.code, message=exc.message)
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(by_alias=True))