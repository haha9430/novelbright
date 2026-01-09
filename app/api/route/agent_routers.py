from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.deps import get_agent_service
from app.service.agent_service import AgentService

router = APIRouter(prefix="/agent", tags=["agent"])


class QueryRequest(BaseModel):
    query: str
    context_limit: Optional[int] = 3


class AddKnowledgeRequest(BaseModel):
    documents: List[str]
    metadatas: Optional[List[Dict[str, Any]]] = None


class QueryResponse(BaseModel):
    query: str
    response: str
    retrieved_documents: List[str]
    document_distances: List[float]
    context_used: str


class KnowledgeResponse(BaseModel):
    status: str
    message: str


class StatsResponse(BaseModel):
    name: str
    count: int
    metadata: Dict[str, Any]



@router.post("/query", response_model=QueryResponse)
async def process_query(
    request: QueryRequest,
    agent_service: AgentService = Depends(get_agent_service)
):
    try:
        result = agent_service.process_query(
            query=request.query,
            context_limit=request.context_limit
        )
        return QueryResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Query processing failed: {str(e)}")


@router.post("/knowledge", response_model=KnowledgeResponse)
async def add_knowledge(
    request: AddKnowledgeRequest,
    agent_service: AgentService = Depends(get_agent_service)
):
    try:
        result = agent_service.add_knowledge(
            documents=request.documents,
            metadatas=request.metadatas
        )
        return KnowledgeResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Adding knowledge failed: {str(e)}")


@router.get("/stats", response_model=StatsResponse)
async def get_knowledge_stats(
    agent_service: AgentService = Depends(get_agent_service)
):
    try:
        stats = agent_service.get_knowledge_stats()
        return StatsResponse(**stats)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


@router.delete("/knowledge/{doc_id}")
async def delete_knowledge(
    doc_id: str,
    agent_service: AgentService = Depends(get_agent_service)
):
    try:
        agent_service.vector_service.delete_document(doc_id)
        return {"status": "success", "message": f"Document {doc_id} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Deletion failed: {str(e)}")


@router.get("/health")
async def health_check():
    return {"status": "healthy", "message": "Agent service is running"}