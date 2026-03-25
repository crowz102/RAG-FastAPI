# Dockerfile cho RAG FastAPI

FROM python:3.11-slim

WORKDIR /app

# Cai dat build dependencies cho psycopg2 va cac thu vien khac
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Port cho FastAPI
EXPOSE 8000

# Script mac dinh (se duoc override trong docker-compose cho worker)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
