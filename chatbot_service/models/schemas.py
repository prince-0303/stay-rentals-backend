from pydantic import BaseModel

class FAQRequest(BaseModel):
    question: str
    session_id: str | None = None

class FAQResponse(BaseModel):
    answer: str
    sources: list[str] = []
    confident: bool = True