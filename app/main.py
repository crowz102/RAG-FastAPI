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

@app.get("/")
def root():
    return {"message": "RAG Chatbot API is running!"}

app.include_router(api_router)