from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import faq_bot, recommendations
from decouple import config

app = FastAPI(title="Rental Platform FAQ Bot")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(faq_bot.router, prefix="/api/faq", tags=["FAQ Bot"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])

@app.get("/health")
def health():
    return {"status": "ok"}