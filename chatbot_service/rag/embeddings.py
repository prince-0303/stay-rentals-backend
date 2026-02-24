from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma

def get_vectorstore():
    embeddings = HuggingFaceEmbeddings(
        model_name="all-MiniLM-L6-v2"
    )
    return Chroma(
        collection_name="faq_docs",
        embedding_function=embeddings,
        persist_directory="./chroma_db"
    )