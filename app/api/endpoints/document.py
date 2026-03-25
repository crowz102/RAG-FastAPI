from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.payloads import IngestResponse
from app.services.ingest import ingest_doc

router = APIRouter()

@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(file: UploadFile = File(...)):
    filename = file.filename.lower()
    if not (filename.endswith(".pdf") or filename.endswith(".docx") or filename.endswith(".docxx") or filename.endswith(".html")):
        raise HTTPException(status_code=400, detail="Chỉ hỗ trợ file PDF, DOCX, hoặc HTML.")
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="File rỗng.")
    try:
        chunks_stored = ingest_doc(file_bytes, filename=file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return IngestResponse(message="Ingestion thành công!", chunks_stored=chunks_stored, filename=file.filename)
