from fastapi import APIRouter, Depends
from app.schemas.payloads import HistoryResponse, HistoryItem
from app.db.database import get_all_sessions, get_messages, delete_session
from app.api.endpoints.auth import get_current_user

router = APIRouter()

@router.get("/sessions")
def list_sessions(current_user: dict = Depends(get_current_user)):
    return get_all_sessions(user_id=current_user["id"])

@router.get("/history/{session_id}", response_model=HistoryResponse)
def get_history(session_id: str, current_user: dict = Depends(get_current_user)):
    messages = get_messages(session_id)
    return HistoryResponse(
        session_id=session_id,
        messages=[HistoryItem(role=m["role"], content=m["content"]) for m in messages],
    )

@router.delete("/history/{session_id}")
def clear_history(session_id: str, current_user: dict = Depends(get_current_user)):
    delete_session(user_id=current_user["id"], session_id=session_id)
    return {"message": f"Đã xóa session '{session_id}'."}
