from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import faq_bot
from decouple import config

app = FastAPI(title="Rental Platform FAQ Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(faq_bot.router, prefix="/api/faq", tags=["FAQ Bot"])

@app.get("/health")
def health():
    return {"status": "ok"}