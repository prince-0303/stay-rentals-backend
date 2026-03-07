from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from rag.embeddings import get_vectorstore
from decouple import config
import json

PROMPT_TEMPLATE = """
You are a helpful support assistant for an accommodation rental platform.
Answer the user's question using ONLY the context provided below.
If the answer is not in the context, say "I don't have information on that.
Please contact our support team."
Do not make up any information.
Context:
{context}
Question: {question}
Answer:
"""

PROPERTY_INTENT_PROMPT = """
You are an intent detector for a rental platform chatbot.
Given a user message, determine if they are searching for a property/accommodation.

User message: {question}

If this is a property search query, extract filters and respond ONLY with valid JSON like:
{{
  "is_property_query": true,
  "city": "Kochi" or null,
  "property_type": "pg" or "apartment" or "house" or "room" or "villa" or "hostel" or null,
  "max_budget": 10000 or null,
  "min_budget": null or number,
  "amenities": ["wifi", "parking"] or []
}}

If this is NOT a property search query (general FAQ, policy question, etc.), respond ONLY with:
{{"is_property_query": false}}

Respond with JSON only. No explanation.
"""

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)


def detect_property_intent(question: str):
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=config("GROQ_API_KEY")
    )
    prompt = PromptTemplate(
        template=PROPERTY_INTENT_PROMPT,
        input_variables=["question"]
    )
    chain = prompt | llm | StrOutputParser()
    result = chain.invoke({"question": question})

    try:
        # Clean up any markdown code blocks if present
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


def get_faq_answer(question: str):
    # Step 1: detect intent
    intent = detect_property_intent(question)
    is_property_query = intent.get("is_property_query", False)
    redirect = build_redirect_url(intent) if is_property_query else None

    # Step 2: answer via RAG as usual
    vectorstore = get_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    prompt = PromptTemplate(
        template=PROMPT_TEMPLATE,
        input_variables=["context", "question"]
    )
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=config("GROQ_API_KEY")
    )
    chain = (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | StrOutputParser()
    )
    docs = retriever.invoke(question)
    sources = [doc.metadata.get("source", "") for doc in docs]
    answer = chain.invoke(question)
    confident = "contact our support" not in answer.lower()

    return answer, sources, confident, is_property_query, redirect