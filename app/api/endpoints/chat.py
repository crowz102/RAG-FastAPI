from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import json
from app.schemas.payloads import ChatRequest, ChatResponse
from app.db.database import get_or_create_session, get_messages, save_message
from app.services.retriever import retrieve
from app.services.llm import generate_answer_stream
from app.api.endpoints.auth import get_current_user

router = APIRouter()

@router.post("/chat")
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    get_or_create_session(user_id=current_user["id"], session_id=request.session_id, first_message=request.question)
    history = get_messages(request.session_id)
    contexts = retrieve(request.question, top_k=request.top_k, filenames=request.filenames)
    
    async def event_generator():
        sources = list({c["filename"] for c in contexts})
        meta = {"session_id": request.session_id, "sources": sources, "type": "meta"}
        yield f"data: {json.dumps(meta)}\n\n"
        
        full_answer = ""
        async for chunk in generate_answer_stream(request.question, contexts, history):
            full_answer += chunk
            yield f"data: {json.dumps({'chunk': chunk, 'type': 'text'})}\n\n"
            
        save_message(request.session_id, "user", request.question)
        save_message(request.session_id, "assistant", full_answer)
        yield "data: [DONE]\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
