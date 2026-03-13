from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag.embeddings import get_vectorstore
from rag.property_embeddings import get_property_vectorstore
from decouple import config
import json

# ── Cached singletons (loaded once at startup) ──────────────────────────────
_faq_vectorstore = None
_llm = None

def get_llm():
    global _llm
    if _llm is None:
        _llm = ChatGroq(
            model="llama-3.3-70b-versatile",
            groq_api_key=config("GROQ_API_KEY"),
            temperature=0.3,
        )
    return _llm

def get_faq_store():
    global _faq_vectorstore
    if _faq_vectorstore is None:
        _faq_vectorstore = get_vectorstore()
    return _faq_vectorstore

def get_property_store():
    # Always fresh to avoid stale collection after sync
    return get_property_vectorstore()

# ── Prompts ──────────────────────────────────────────────────────────────────
UNIFIED_PROMPT = """You are a helpful AI concierge for Ez-Stay, an accommodation rental platform.

Previous conversation:
{history}

FAQ Knowledge:
{faq_context}

Available Properties from our database:
{property_context}

User question: {question}

Instructions:
- If the user is asking about properties/accommodation, describe the matching properties from "Available Properties" above with their title, price, location and key features.
- If Available Properties shows "No properties found", say you could not find matches and suggest using the View Recommendations button.
- If the user is asking about policies/procedures, answer from FAQ Knowledge.
- Be conversational and helpful. Max 4 sentences.

Answer:"""

INTENT_PROMPT = """Classify this user message for a rental platform chatbot.

Message: {question}

Respond ONLY with valid JSON:
- If property search: {{"is_property_query": true, "city": "cityname or null", "property_type": "pg/apartment/house/room/villa/hostel or null", "max_budget": number_or_null, "min_budget": number_or_null, "amenities": []}}
- Otherwise: {{"is_property_query": false}}

JSON only, no explanation."""

# ── Helpers ──────────────────────────────────────────────────────────────────
def format_docs(docs):
    if not docs:
        return "No properties found."
    return "\n\n".join(doc.page_content for doc in docs)

def format_history(history: list) -> str:
    if not history:
        return "No previous conversation."
    lines = []
    for msg in history[-6:]:
        role = "User" if msg["role"] == "user" else "Assistant"
        lines.append(f"{role}: {msg['text']}")
    return "\n".join(lines)

def detect_intent(question: str) -> dict:
    try:
        llm = get_llm()
        prompt = PromptTemplate(template=INTENT_PROMPT, input_variables=["question"])
        chain = prompt | llm | StrOutputParser()
        result = chain.invoke({"question": question})
        result = result.strip().replace("```json", "").replace("```", "").strip()
        return json.loads(result)
    except Exception:
        return {"is_property_query": False}

def build_redirect_url(intent: dict) -> str:
    params = []
    if intent.get("city"):
        params.append(f"city={intent['city']}")
    if intent.get("property_type"):
        params.append(f"property_type={intent['property_type']}")
    if intent.get("max_budget"):
        params.append(f"max_budget={intent['max_budget']}")
    if intent.get("min_budget"):
        params.append(f"min_budget={intent['min_budget']}")
    if intent.get("amenities"):
        params.append(f"amenities={','.join(intent['amenities'])}")
    base = "/recommendations"
    return f"{base}?{'&'.join(params)}" if params else base

# ── Main entry point ─────────────────────────────────────────────────────────
def get_faq_answer(question: str, history: list = None):
    if history is None:
        history = []

    # Step 1: detect intent
    intent = detect_intent(question)
    is_property_query = intent.get("is_property_query", False)
    redirect = build_redirect_url(intent) if is_property_query else None

    # Step 2: retrieve FAQ context always
    faq_retriever = get_faq_store().as_retriever(search_kwargs={"k": 3})
    faq_docs = faq_retriever.invoke(question)
    faq_context = format_docs(faq_docs)

    # Step 3: retrieve property context only if property query
    property_context = "No properties found."
    if is_property_query:
        try:
            prop_store = get_property_store()
            property_retriever = prop_store.as_retriever(search_kwargs={"k": 3})
            property_docs = property_retriever.invoke(question)
            property_context = format_docs(property_docs)
        except Exception:
            property_context = "No properties found."

    # Step 4: single LLM call
    llm = get_llm()
    prompt = PromptTemplate(
        template=UNIFIED_PROMPT,
        input_variables=["history", "faq_context", "property_context", "question"]
    )
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({
        "history": format_history(history),
        "faq_context": faq_context,
        "property_context": property_context,
        "question": question,
    })

    sources = [doc.metadata.get("source", "") for doc in faq_docs]
    confident = "contact our support" not in answer.lower()

    return answer, sources, confident, is_property_query, redirect