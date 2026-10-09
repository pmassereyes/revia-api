# main.py - RevIA API
from fastapi import FastAPI
from app.routers import health

app = FastAPI(title="RevIA API", version="0.1.0")
app.include_router(health.router)