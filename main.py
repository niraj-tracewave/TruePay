import os
from contextlib import asynccontextmanager

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.admin.admin_auth import router as admin_auth_router
from app.admin.admin_credit import router as admin_credit_router
from app.admin.admin_dashboard import router as admin_dashboard_router
from app.admin.admin_loan import router as admin_loan_router
from app.admin.admin_emi_schedule import router as admin_emi_schedule_router
from app.user.user_auth import router as user_auth_router
from app.user.user_loan import router as user_loan_router
from app.user.user_surpass import router as surpass_router
from app.user.user_razorpay import router as razorpay_router
from app.user.user_webhook import router as webhook_router
from common.cache_string import refresh_cache_strings
from common.response import validation_exception_handler
from config import app_config
from custom_middleware.auth_middleware import AuthMiddleware
from db_domains import db


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event manager for startup and shutdown tasks."""
    db.init_db()
    print("Initializing database...")
    yield
    print("Shutting down...")


app = FastAPI(
    title="True Pay",
    root_path="/api/base",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)
load_dotenv()

app.add_middleware(AuthMiddleware)
app.add_exception_handler(RequestValidationError, validation_exception_handler)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MEDIA_DIR = os.path.abspath("media")
os.makedirs(MEDIA_DIR, exist_ok=True)

app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

# User Routers
app.include_router(user_auth_router)
app.include_router(user_loan_router)
app.include_router(admin_auth_router)
app.include_router(admin_loan_router)
app.include_router(admin_credit_router)
app.include_router(admin_dashboard_router)

app.include_router(surpass_router)
app.include_router(razorpay_router)
app.include_router(webhook_router)

app.include_router(admin_emi_schedule_router)

if __name__ == "__main__":
    refresh_cache_strings()
    uvicorn.run(
        "main:app",
        host=app_config.HOST_URL,
        port=app_config.HOST_PORT,
        log_level="info",
        reload=True
    )
