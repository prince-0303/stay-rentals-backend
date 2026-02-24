from langchain_groq import ChatGroq
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from rag.embeddings import get_vectorstore
from decouple import config

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

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

def get_faq_answer(question: str):
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

    # Get source documents separately for metadata
    docs = retriever.invoke(question)
    sources = [doc.metadata.get("source", "") for doc in docs]

    answer = chain.invoke(question)
    confident = "contact our support" not in answer.lower()

    return answer, sources, confident