from typing import List, Dict, Any
from openai import OpenAI # openai==1.52.2
from app.service.vector_service import VectorService
from app.core.settings import upstage_settings


class AgentService:
    def __init__(self, vector_service: VectorService):
        self.client = OpenAI(api_key=upstage_settings.api_key, base_url=upstage_settings.base_url)
        self.vector_service = vector_service
    
    def process_query(self, query: str, context_limit: int = 3) -> Dict[str, Any]:
        # Step 1: Retrieve relevant documents using vector search
        search_results = self.vector_service.search(query, n_results=context_limit)
        
        # Step 2: Prepare context from retrieved documents
        context = self._prepare_context(search_results)
        
        # Step 3: Generate response using Upstage Solar LLM
        response = self._generate_response(query, context)
        
        return {
            "query": query,
            "response": response,
            "retrieved_documents": search_results["documents"],
            "document_distances": search_results["distances"],
            "context_used": context
        }
    
    def _prepare_context(self, search_results: Dict[str, Any]) -> str:
        documents = search_results["documents"]
        metadatas = search_results["metadatas"]
        
        context_parts = []
        for i, doc in enumerate(documents):
            metadata = metadatas[i] if metadatas else {}
            context_part = f"Document {i+1}:\n{doc}\n"
            if metadata:
                context_part += f"Metadata: {metadata}\n"
            context_parts.append(context_part)
        
        return "\n".join(context_parts)
    
    def _generate_response(self, query: str, context: str) -> str:
        system_prompt = """You are a helpful AI assistant. Use the provided context to answer the user's question accurately and concisely. 
        If the context doesn't contain enough information to answer the question, say so clearly."""
        
        user_prompt = f"""Context:
{context}

Question: {query}

Please provide a helpful response based on the context above."""
        
        try:
            response = self.client.chat.completions.create(
                model=upstage_settings.chat_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=500
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def add_knowledge(self, documents: List[str], metadatas: List[Dict[str, Any]] = None) -> Dict[str, str]:
        try:
            self.vector_service.add_documents(documents, metadatas)
            return {"status": "success", "message": f"Added {len(documents)} documents to knowledge base"}
        except Exception as e:
            return {"status": "error", "message": f"Failed to add documents: {str(e)}"}
    
    def get_knowledge_stats(self) -> Dict[str, Any]:
        return self.vector_service.get_collection_info()