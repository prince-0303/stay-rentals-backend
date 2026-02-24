from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from rag.embeddings import get_vectorstore

def ingest():
    loader = DirectoryLoader(
        "./docs",
        glob="**/*.txt",
        loader_cls=TextLoader
    )
    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=400,
        chunk_overlap=50
    )
    chunks = splitter.split_documents(documents)

    vectorstore = get_vectorstore()
    vectorstore.add_documents(chunks)

    print(f"Ingested {len(chunks)} chunks from {len(documents)} documents")

if __name__ == "__main__":
    ingest()