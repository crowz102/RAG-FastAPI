from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.payloads import IngestResponse
from app.services.ingest import ingest_doc

router = APIRouter()

from app.api.endpoints.auth import get_current_user
from fastapi import Depends
import uuid
from datetime import datetime
from app.db.database import get_conn
from app.worker import ingest_task

@router.post("/ingest", response_model=dict) # Tra ve dict vi structure thay doi
async def ingest_document(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx") or filename.endswith(".docxx") or filename.endswith(".html")):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF, DOCX, hoặc HTML.")
    
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File rỗng.")

    # 0. Tính MD5 Hash để kiểm tra trùng lặp nội dung
    import hashlib
    file_hash = hashlib.md5(file_bytes).hexdigest()

    # 1. Kiểm tra tồn tại TRƯỚC KHI xử lý (Tiết kiệm tài nguyên)
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Nếu User này đã up file y hệt nội dung và đã xong -> Trả về luôn
                cur.execute(
                    "SELECT id, status FROM documents WHERE user_id = %s AND file_hash = %s",
                    (current_user["id"], file_hash)
                )
                existing = cur.fetchone()
                if existing:
                    if existing["status"] == 'completed':
                        return {
                            "message": "Tài liệu này đã được nạp và sẵn sàng!",
                            "doc_id": existing["id"],
                            "filename": file.filename,
                            "status": "completed",
                            "already_exists": True
                        }
                    elif existing["status"] == 'processing':
                        return {
                            "message": "Tài liệu này đang được xử lý ngầm, vui lòng đợi!",
                            "doc_id": existing["id"],
                            "filename": file.filename,
                            "status": "processing"
                        }

                # 1.1 Kiểm tra và dọn dẹp Metadata cũ nếu trùng tên (nhưng khác hash)
                # Kiểm tra xem file hash này đã tồn tại ở bất kỳ User nào khác chưa (Cross-user duplicate)
                is_duplicate = False
                cur.execute("SELECT id FROM documents WHERE file_hash = %s AND user_id != %s", (file_hash, current_user["id"]))
                if cur.fetchone():
                    is_duplicate = True

                # Xóa bản ghi cũ của CÙNG User + CÙNG Filename để tránh trùng lặp trong danh sách
                cur.execute("DELETE FROM documents WHERE user_id = %s AND filename = %s", (current_user["id"], file.filename))
                
                # Chèn bản ghi mới
                doc_id = str(uuid.uuid4())
                now = datetime.now().isoformat()
                cur.execute(
                    "INSERT INTO documents (id, user_id, filename, file_hash, is_duplicate, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (doc_id, current_user["id"], file.filename, file_hash, is_duplicate, "processing", now)
                )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Lỗi xử lý Metadata: {str(e)}")

    # 2. Đẩy task vào Celery (Background) - Chỉ khi thực sự cần thiết
    task = ingest_task.delay(file_bytes, file.filename, current_user["id"], doc_id)
    
    return {
        "message": "Đã bắt đầu xử lý tài liệu mới!",
        "task_id": task.id,
        "doc_id": doc_id,
        "filename": file.filename,
        "status": "processing"
    }
