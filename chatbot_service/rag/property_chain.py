from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from rag.property_embeddings import get_property_vectorstore
from decouple import config

SEARCH_PROMPT = """
You are a property recommendation assistant.
The user is looking for: {question}

Matching properties from our database:
{context}

Return ONLY properties that actually match the query. 
Be concise - 2-3 sentences max.
If a property doesn't match, don't mention it.
Format: Property name, price, why it matches.
"""

def search_properties(query: str):
    vectorstore = get_property_vectorstore()
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    docs = retriever.invoke(query)

    if not docs:
        return [], "No matching properties found."

    context = "\n\n".join(doc.page_content for doc in docs)
    property_ids = [doc.metadata.get("property_id") for doc in docs]

    prompt = PromptTemplate(
        template=SEARCH_PROMPT,
        input_variables=["question", "context"]
    )
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=config("GROQ_API_KEY")
    )
    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({"question": query, "context": context})

    return property_ids, answer


def compare_properties(properties_text: str, preference: str = ""):
    prompt = PromptTemplate(
        template=COMPARE_PROMPT,
        input_variables=["properties", "preference"]
    )
    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        groq_api_key=config("GROQ_API_KEY")
    )
    chain = prompt | llm | StrOutputParser()
    return chain.invoke({"properties": properties_text, "preference": preference})