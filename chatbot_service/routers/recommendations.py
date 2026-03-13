from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from rag.property_chain import search_properties, compare_properties
from rag.property_embeddings import get_property_vectorstore
from langchain_core.documents import Document
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class SearchRequest(BaseModel):
    query: str

class CompareRequest(BaseModel):
    properties: list[dict]
    preference: str = ""

class SyncRequest(BaseModel):
    properties: list[dict]

@router.post("/search/")
def ai_property_search(request: SearchRequest):
    try:
        property_ids, answer = search_properties(request.query)
        return {"property_ids": property_ids, "answer": answer}
    except Exception as e:
        logger.error(f"AI search error: {e}")
        raise HTTPException(status_code=500, detail="AI search failed.")

@router.post("/compare/")
def ai_property_compare(request: CompareRequest):
    try:
        properties_text = "\n\n".join([
            f"Property {i+1}: {p['title']}\n"
            f"Price: Rs.{p['rent_price']}/month\n"
            f"Location: {p['city']}, {p['state']}\n"
            f"Type: {p['property_type']} | Room: {p['room_type']}\n"
            f"Amenities: {', '.join(p.get('amenities', []))}\n"
            f"Rating: {p.get('avg_rating', 'N/A')}"
            for i, p in enumerate(request.properties)
        ])
        answer = compare_properties(properties_text, request.preference)
        return {"recommendation": answer}
    except Exception as e:
        logger.error(f"Compare error: {e}")
        raise HTTPException(status_code=500, detail="Comparison failed.")

@router.post("/sync/")
def sync_properties(request: SyncRequest):
    try:
        import rag.chain as chain_module

        vectorstore = get_property_vectorstore()
        docs = []
        for p in request.properties:
            content = (
                f"Title: {p['title']}\n"
                f"Type: {p['property_type']} | Room: {p['room_type']}\n"
                f"Location: {p['city']}, {p['state']}\n"
                f"Price: Rs.{p['rent_price']}/month\n"
                f"Amenities: {', '.join(p.get('amenities', []))}\n"
                f"Furnishing: {p.get('furnishing_status', '')}\n"
                f"Preferred Tenants: {p.get('preferred_tenants', '')}\n"
                f"Description: {p.get('description', '')}"
            )
            docs.append(Document(
                page_content=content,
                metadata={"property_id": str(p["id"]), "title": p["title"]}
            ))

        # Delete and recreate collection
        vectorstore.delete_collection()

        # Reset singleton so next request gets fresh vectorstore
        chain_module._property_vectorstore = None

        # Create fresh and add docs
        fresh_store = get_property_vectorstore()
        fresh_store.add_documents(docs)

        # Update singleton with fresh store
        chain_module._property_vectorstore = fresh_store

        logger.info(f"Synced {len(docs)} properties to vectorstore")
        return {"synced": len(docs)}
    except Exception as e:
        logger.error(f"Sync error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Sync failed.")
