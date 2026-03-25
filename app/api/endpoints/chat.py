from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
import json
from app.schemas.payloads import ChatRequest, ChatResponse
from app.db.database import get_or_create_session, get_messages, save_message
from app.services.retriever import retrieve
from app.services.llm import generate_answer_stream, contextualize_question
from app.api.endpoints.auth import get_current_user

router = APIRouter()

# Counter so luong SSE stream dang mo (bao gom ca heartbeat presence)
global_online_users = 0

@router.get("/presence/ping")
async def presence_ping(token: str = ""):
    """SSE heartbeat ket noi song de dem so User dang mo tab."""
    import asyncio
    from app.core.security import decode_token
    
    # Xac thuc token truyen qua query param (EventSource khong ho tro custom headers)
    try:
        payload = decode_token(token)
        if not payload:
            from fastapi import HTTPException
            raise HTTPException(status_code=401, detail="Token khong hop le")
    except Exception:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Token khong hop le")
    
    async def heartbeat():
        global global_online_users
        global_online_users += 1
        try:
            while True:
                yield "data: ping\n\n"
                await asyncio.sleep(10)
        finally:
            global_online_users = max(0, global_online_users - 1)
    return StreamingResponse(heartbeat(), media_type="text/event-stream")

@router.post("/chat")
async def chat(request: ChatRequest, current_user: dict = Depends(get_current_user)):
    get_or_create_session(user_id=current_user["id"], session_id=request.session_id, first_message=request.question)
    history = get_messages(request.session_id)
    user_api_key = current_user.get("api_key")
    
    search_query = await contextualize_question(request.question, history, user_api_key)
    contexts = await retrieve(search_query, top_k=request.top_k, filenames=request.filenames, user_id=current_user["id"])
    
    async def event_generator():
        global global_online_users
        global_online_users += 1
        try:
            sources = list({c["filename"] for c in contexts})
            meta = {"session_id": request.session_id, "sources": sources, "type": "meta"}
            yield f"data: {json.dumps(meta)}\n\n"
            
            full_answer = ""
            async for chunk in generate_answer_stream(request.question, contexts, history, user_api_key):
                full_answer += chunk
                yield f"data: {json.dumps({'chunk': chunk, 'type': 'text'})}\n\n"
                
            save_message(request.session_id, "user", request.question)
            save_message(request.session_id, "assistant", full_answer)
            yield "data: [DONE]\n\n"
        finally:
            global_online_users = max(0, global_online_users - 1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
