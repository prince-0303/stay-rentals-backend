from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import faq_bot, recommendations
from decouple import config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ez-Stay AI Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost", "http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(faq_bot.router, prefix="/api/faq", tags=["FAQ Bot"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])

@app.on_event("startup")
async def startup_event():
    """Preload embeddings and vectorstores at startup to avoid cold start lag."""
    try:
        logger.info("Preloading embeddings and vectorstores...")
        from rag.chain import get_faq_store, get_property_store, get_llm
        get_faq_store()
        get_property_store()
        get_llm()
        logger.info("Preloading complete. Bot is ready.")
    except Exception as e:
        logger.error(f"Preload failed: {e}")

@app.get("/health")
def health():
    return {"status": "ok"}