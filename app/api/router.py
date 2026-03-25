from fastapi import APIRouter
from app.api.endpoints import document, chat, history, auth, admin
from app.services.retriever import retrieve
from app.core.config import COLLECTION_NAME

api_router = APIRouter()
api_router.include_router(auth.router, tags=["Auth"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin"])
api_router.include_router(document.router, tags=["Document"])
api_router.include_router(chat.router, tags=["Chat"])
api_router.include_router(history.router, tags=["History"])


from app.api.endpoints.auth import get_current_user
from fastapi import Depends
from qdrant_client.models import Filter, FieldCondition, MatchValue

@api_router.get("/documents")
def list_documents(current_user: dict = Depends(get_current_user)):
    """Lấy danh sách tên file đã ingest trong Qdrant từ DB Metadata."""
    from app.db.database import get_conn
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT filename, status, created_at FROM documents WHERE user_id = %s ORDER BY created_at DESC", 
                    (current_user["id"],)
                )
                rows = cur.fetchall()
                return {"documents": [dict(r) for r in rows]}
    except Exception:
        return {"documents": []}


@api_router.get("/debug/search")
async def debug_search(question: str, top_k: int = 3):
    contexts = await retrieve(question, top_k=top_k)
    return {"question": question, "chunks_found": len(contexts), "chunks": contexts}