import os
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

# Get origins from env var
cors_origins_str = os.getenv(
    "CORS_ORIGINS",
    "http://localhost:3000,http://localhost:5174"
)

# Split by comma and strip whitespace and trailing slashes
origins = [
    origin.strip().rstrip("/")
    for origin in cors_origins_str.split(",")
    if origin.strip()
]

# Add both with and without trailing slash for each origin
all_origins = []
for origin in origins:
    all_origins.append(origin)
    all_origins.append(origin + "/")

app.add_middleware(
    CORSMiddleware,
    allow_origins=all_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(appeals.router, prefix="/appeals", tags=["appeals"])
app.include_router(cases.router, prefix="/cases", tags=["cases"])
app.include_router(eval.router, prefix="/eval", tags=["eval"])
app.include_router(health.router, tags=["health"])
