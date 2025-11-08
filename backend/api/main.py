import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config import settings
from api.routes import appeals, cases, eval, health

log = structlog.get_logger()

app = FastAPI(
    title="Prior Authorization Appeal Agent",
    version="1.0.0",
    docs_url="/docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(appeals.router, prefix="/appeals", tags=["appeals"])
app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(eval.router, prefix="/eval", tags=["eval"])
app.include_router(health.router, tags=["health"])
