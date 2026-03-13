from fastapi import APIRouter, HTTPException
from models.schemas import FAQRequest, FAQResponse
from rag.chain import get_faq_answer
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory session store (per session_id)
# For production, use Redis
_sessions: dict = {}

@router.post("/", response_model=FAQResponse)
def ask_faq(request: FAQRequest):
    try:
        # Get conversation history for this session
        session_id = getattr(request, 'session_id', None) or 'default'
        history = _sessions.get(session_id, [])

        answer, sources, confident, is_property_query, redirect = get_faq_answer(
            request.question,
            history=history
        )

        # Update history
        history.append({"role": "user", "text": request.question})
        history.append({"role": "bot", "text": answer})
        # Keep last 20 messages only
        _sessions[session_id] = history[-20:]

        return FAQResponse(
            answer=answer,
            sources=sources,
            confident=confident,
            is_property_query=is_property_query,
            redirect=redirect
        )
    except Exception as e:
        logger.error(f"FAQ chain error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Something went wrong.")

@router.delete("/session/{session_id}")
def clear_session(session_id: str):
    _sessions.pop(session_id, None)
    return {"message": "Session cleared"}