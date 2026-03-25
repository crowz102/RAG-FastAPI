from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.db.database import init_db
from app.api.router import api_router

app = FastAPI(
    title="RAG Chatbot API",
    description="Upload tài liệu và hỏi đáp dựa trên nội dung tài liệu.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def startup():
    init_db()

from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def root():
    return FileResponse(os.path.join("frontend", "index.html"))

@app.get("/admin")
@app.get("/admin.html")
def admin_page():
    return FileResponse(os.path.join("frontend", "admin.html"))

app.include_router(api_router)