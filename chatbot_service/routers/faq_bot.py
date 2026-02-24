from fastapi import APIRouter, HTTPException
from models.schemas import FAQRequest, FAQResponse
from rag.chain import get_faq_answer
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/", response_model=FAQResponse)
def ask_faq(request: FAQRequest):
    try:
        answer, sources, confident = get_faq_answer(request.question)
        return FAQResponse(
            answer=answer,
            sources=sources,
            confident=confident
        )
    except Exception as e:
        logger.error(f"FAQ chain error: {e}")
        raise HTTPException(
            status_code=500,
            detail="Something went wrong while processing your question. Please try again."
        )