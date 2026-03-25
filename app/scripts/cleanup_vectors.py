import os
import psycopg2
from qdrant_client import QdrantClient
from qdrant_client.models import Filter, FieldCondition, MatchValue

# Lay thong tin tu bien moi truong neu co
DATABASE_URL = os.getenv("DATABASE_URL")
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "rag_collection")

def cleanup():
    print(f"🧹 Bat dau quy trinh bao tri Vector DB ({COLLECTION_NAME})...")
    
    # 1. Ket noi Postgres - Source of Truth
    try:
        conn = psycopg2.connect(DATABASE_URL)
        cur = conn.cursor()
        cur.execute("SELECT filename FROM documents")
        sql_files = {row[0] for row in cur.fetchall()}
        cur.close()
        conn.close()
        print(f"📜 Tim thay {len(sql_files)} file trong Database SQL.")
    except Exception as e:
        print(f"❌ Loi ket noi SQL: {e}")
        return

    # 2. Ket noi Qdrant
    try:
        client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
        # Lay moi Point de kiem tra metadata
        # Lay theo scroll cho den khi het
        offset = None
        qdrant_files = set()
        
        print("🔍 Dang quét Vector DB để tìm các tài liệu mồ côi...")
        
        while True:
            scroll_result = client.scroll(
                collection_name=COLLECTION_NAME,
                limit=100,
                with_payload=True,
                with_vectors=False,
                offset=offset
            )
            points, next_offset = scroll_result
            
            for p in points:
                fname = p.payload.get("filename")
                if fname:
                    qdrant_files.add(fname)
            
            if next_offset is None:
                break
            offset = next_offset

        # 3. So sanh va xoa
        orphaned = qdrant_files - sql_files
        
        if not orphaned:
            print("✅ Tuyet voi! Khong co vector mo coi nao. He thong dang rat sach se.")
            return

        print(f"🔥 Phat hien {len(orphaned)} file mo coi trong Qdrant: {orphaned}")
        
        for fname in orphaned:
            print(f"🗑️ Dang xoa vector cua file: {fname}...")
            client.delete(
                collection_name=COLLECTION_NAME,
                points_selector=Filter(
                    must=[FieldCondition(key="filename", match=MatchValue(value=fname))]
                )
            )
        
        print("✨ Hoan tat quy trinh bao tri.")

    except Exception as e:
        print(f"❌ Loi thao tac Qdrant: {e}")

if __name__ == "__main__":
    if not DATABASE_URL:
        print("⚠️ DATABASE_URL khong duoc thiet lap. Hay export DATABASE_URL='...' truoc khi chay.")
    else:
        cleanup()
