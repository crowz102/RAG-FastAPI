from fastapi import APIRouter
from app.api.endpoints import document, chat, history, auth
from app.services.retriever import retrieve

api_router = APIRouter()
api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(document.router, tags=["Document"])
api_router.include_router(chat.router, tags=["Chat"])
api_router.include_router(history.router, tags=["History"])

@api_router.get("/debug/search")
def debug_search(question: str, top_k: int = 3):
    contexts = retrieve(question, top_k=top_k)
    return {"question": question, "chunks_found": len(contexts), "chunks": contexts}
