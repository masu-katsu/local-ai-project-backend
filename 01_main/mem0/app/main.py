from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import logging

app = FastAPI(title="Mem0 Memory Service")
logger = logging.getLogger(__name__)

class Memory(BaseModel):
    memory_id: str
    content: str
    importance: float
    category: str
    user_id: str
    timestamp: str
    source: str
    access_count: int
    last_accessed: str

# インメモリストレージ（実際はDBを使用）
memories: List[Memory] = []

@app.post("/memories")
async def create_memory(memory: Memory) -> dict:
    memories.append(memory)
    logger.info(f"記憶作成: {memory.memory_id}")
    return {"status": "created", "memory_id": memory.memory_id}

@app.get("/memories/{user_id}")
async def get_memories(user_id: str, category: Optional[str] = None) -> List[Memory]:
    user_memories = [m for m in memories if m.user_id == user_id]
    if category:
        user_memories = [m for m in user_memories if m.category == category]
    return user_memories

@app.get("/memories/search/{user_id}")
async def search_memories(user_id: str, query: str, top_k: int = 5) -> List[Memory]:
    # 簡易検索（実際はベクトル検索）
    user_memories = [m for m in memories if m.user_id == user_id]
    results = [m for m in user_memories if query.lower() in m.content.lower()]
    return results[:top_k]

@app.put("/memories/{memory_id}/importance")
async def update_importance(memory_id: str, delta: float = 0.1) -> dict:
    for memory in memories:
        if memory.memory_id == memory_id:
            memory.importance = min(1.0, max(0.0, memory.importance + delta))
            memory.access_count += 1
            return {"status": "updated", "importance": memory.importance}
    return {"status": "not_found"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "mem0"}
