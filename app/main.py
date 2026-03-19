from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.models import ChatRequest, ChatResponse, HistoryResponse, HistoryItem, IngestResponse
from app.ingest import ingest_pdf
from app.retriever import retrieve
from app.llm import generate_answer
from app.database import init_db, get_all_sessions, get_or_create_session, delete_session, save_message, get_messages

app = FastAPI(
    title="RAG Chatbot API",
    description="Upload tài liệu PDF và hỏi đáp dựa trên nội dung tài liệu.",
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

@app.post("/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF.")
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File rỗng.")
    try:
        chunks_stored = ingest_pdf(file_bytes, filename=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return IngestResponse(message="Ingestion thành công!", chunks_stored=chunks_stored, filename=file.filename)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    get_or_create_session(request.session_id, first_message=request.question)
    contexts = retrieve(request.question, top_k=request.top_k)
    answer = generate_answer(request.question, contexts)
    save_message(request.session_id, "user", request.question)
    save_message(request.session_id, "assistant", answer)
    sources = list({c["filename"] for c in contexts})
    return ChatResponse(answer=answer, session_id=request.session_id, sources=sources)

@app.get("/sessions")
def list_sessions():
    return get_all_sessions()

@app.get("/history/{session_id}", response_model=HistoryResponse)
def get_history(session_id: str):
    messages = get_messages(session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[HistoryItem(role=m["role"], content=m["content"]) for m in messages],
    )

@app.delete("/history/{session_id}")
def clear_history(session_id: str):
    delete_session(session_id)
    return {"message": f"Đã xóa session '{session_id}'."}

@app.get("/debug/search")
def debug_search(question: str, top_k: int = 3):
    contexts = retrieve(question, top_k=top_k)
    return {"question": question, "chunks_found": len(contexts), "chunks": contexts}