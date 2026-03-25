import os
from dotenv import load_dotenv

load_dotenv()
# Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Security
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("LỖI: Chưa cấu hình SECRET_KEY trong biến môi trường (.env)")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")) # mặc định 7 ngày
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY")

COLLECTION_NAME = "documents"
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("LỖI: Chưa cấu hình DATABASE_URL trong biến môi trường (.env)")
    
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")
if not ADMIN_PASSWORD:
    raise ValueError("LỖI: Chưa cấu hình ADMIN_PASSWORD trong biến môi trường (.env)")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")