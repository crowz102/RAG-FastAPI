from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.api.endpoints.auth import get_current_admin_user
from app.db.database import get_conn, get_setting, set_setting
from app.schemas.payloads import UserResponse
from pydantic import BaseModel

router = APIRouter()

class UserAdminResponse(UserResponse):
    is_admin: bool
    api_key: str | None

class SettingUpdate(BaseModel):
    key: str
    value: str

@router.get("/users", response_model=List[UserAdminResponse])
def get_all_users(admin: dict = Depends(get_current_admin_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, username, is_admin, api_key FROM users ORDER BY username")
            rows = cur.fetchall()
            return [dict(r) for r in rows]

class KeyUpdate(BaseModel):
    api_key: str

@router.put("/users/{user_id}/key")
def update_user_key(user_id: str, data: KeyUpdate, admin: dict = Depends(get_current_admin_user)):
    with get_conn() as conn:
        with conn.cursor() as cur:
            key = data.api_key.strip() if data.api_key.strip() else None
            cur.execute("UPDATE users SET api_key = %s WHERE id = %s RETURNING id", (key, user_id))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok"}

@router.delete("/users/{user_id}")
def delete_user(user_id: str, admin: dict = Depends(get_current_admin_user)):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="Không thể xoá chính mình!")
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM messages WHERE session_id IN (SELECT id FROM sessions WHERE user_id = %s)", (user_id,))
            cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
            cur.execute("DELETE FROM users WHERE id = %s RETURNING id", (user_id,))
            if not cur.fetchone():
                raise HTTPException(status_code=404, detail="User not found")
    return {"status": "ok"}

@router.get("/settings/{key}")
def get_sys_setting(key: str, admin: dict = Depends(get_current_admin_user)):
    val = get_setting(key, "")
    return {"key": key, "value": val}

@router.put("/settings")
def update_sys_setting(data: SettingUpdate, admin: dict = Depends(get_current_admin_user)):
    set_setting(data.key, data.value)
    return {"status": "ok"}
    
import time
analytics_cache = {"data": None, "last_updated": 0}

@router.get("/analytics")
def get_analytics(admin: dict = Depends(get_current_admin_user)):
    global analytics_cache
    now = time.time()
    
    # Cache trong 3 giây để tránh Database Hammering
    if analytics_cache["data"] and (now - analytics_cache["last_updated"] < 3):
        return analytics_cache["data"]
        
    from app.api.endpoints.chat import global_online_users
    from app.db.database import get_setting, get_conn
    
    groq_calls = int(get_setting("groq_api_calls", "0") or 0)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(id) AS c FROM users")
            total_users = cur.fetchone()["c"]
            cur.execute("SELECT COUNT(id) AS c FROM messages")
            total_messages = cur.fetchone()["c"]
            
    data = {
        "online_users": global_online_users,
        "groq_calls": groq_calls,
        "total_users": total_users,
        "total_messages": total_messages
    }
    
    analytics_cache["data"] = data
    analytics_cache["last_updated"] = now
    return data
    
@router.get("/documents")
def list_admin_documents(admin: dict = Depends(get_current_admin_user)):
    from app.db.database import get_conn
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT d.filename, d.status, d.chunks_count, d.is_duplicate, d.file_hash, d.created_at, u.username
                    FROM documents d
                    JOIN users u ON d.user_id = u.id
                    ORDER BY d.created_at DESC
                """)
                rows = cur.fetchall()
                return {"documents": [dict(r) for r in rows]}
    except Exception:
        return {"documents": []}
        
@router.delete("/documents/{filename}")
def delete_document(filename: str, admin: dict = Depends(get_current_admin_user)):
    from app.services.ingest import get_qdrant_client
    from app.core.config import COLLECTION_NAME
    from qdrant_client.models import Filter, FieldCondition, MatchValue
    from app.db.database import get_conn
    
    # 1. Xóa trong Qdrant (Bọc try-except vì collection mới có thể chưa tồn tại)
    try:
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        client = get_qdrant_client()
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(
                must=[FieldCondition(key="filename", match=MatchValue(value=filename))]
            )
        )
    except Exception as e:
        print(f"Bỏ qua xóa Qdrant (File có thể không tồn tại trên Cloud): {str(e)}")
    
    # 2. Xóa trong MySQL/Postgres Metadata
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM documents WHERE filename = %s", (filename,))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xóa Metadata: {str(e)}")
        
    return {"status": "ok", "deleted_file": filename}
