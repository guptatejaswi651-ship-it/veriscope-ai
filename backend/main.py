import os
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import initialize
from routers.research import router as research_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize()
    yield

app = FastAPI(
    title="VeriScope AI",
    description="Multi-Agent Research and Fact-Checking System",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip().rstrip("/")
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://localhost:5174",
        ).split(",")
        if origin.strip()
    ],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def home():
    return {"message": "Welcome to VeriScope AI Backend!", "status": "running"}

@app.get("/health")
def health():
    return {"status": "healthy", "project": "VeriScope AI"}

# Explicitly register the API router so its operations appear in /docs.
app.include_router(research_router)
