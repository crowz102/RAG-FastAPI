from celery import Celery
from app.core.config import REDIS_URL
from app.services.ingest import ingest_doc
from app.db.database import get_conn
import logging

celery_app = Celery(
    "worker",
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Cấu hình để Celery nhận diện task
celery_app.conf.update(
    task_track_started=True,
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Ho_Chi_Minh',
    enable_utc=True,
)

@celery_app.task(name="ingest_task", bind=True)
def ingest_task(self, file_bytes: bytes, filename: str, user_id: str, doc_id: str):
    logging.info(f"Bắt đầu xử lý file: {filename} cho user: {user_id}")
    try:
        # Thực hiện ingest thực tế
        chunks_count = ingest_doc(file_bytes, filename, user_id)
        
        # Cập nhật DB khi thành công
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET status = 'completed', chunks_count = %s WHERE id = %s",
                    (chunks_count, doc_id)
                )
        return {"status": "success", "chunks": chunks_count}
    except Exception as e:
        logging.error(f"Lỗi Ingest: {str(e)}")
        # Cập nhật DB khi thất bại
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE documents SET status = 'failed', error_message = %s WHERE id = %s",
                    (str(e), doc_id)
                )
        raise e
