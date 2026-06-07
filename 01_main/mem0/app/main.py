from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional
import logging
import chromadb
from chromadb.config import Settings
import os

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

# ChromaDBクライアント初期化
CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))

chroma_client = None
collection = None

@app.on_event("startup")
async def init_chromadb():
    """ChromaDBを初期化"""
    global chroma_client, collection
    try:
        chroma_client = chromadb.HttpClient(
            host=CHROMA_HOST,
            port=CHROMA_PORT,
            settings=Settings(allow_reset=True, anonymized_telemetry=False)
        )
        
        # コレクション作成
        try:
            collection = chroma_client.get_collection("memories")
        except:
            collection = chroma_client.create_collection(
                name="memories",
                metadata={"description": "Mem0記憶ストレージ"}
            )
        
        logger.info("ChromaDB初期化完了")
    except Exception as e:
        logger.error(f"ChromaDB初期化失敗: {e}")
        # フォールバック: インメモリストレージ
        chroma_client = None
        collection = None

@app.post("/memories")
async def create_memory(memory: Memory) -> dict:
    """記憶を保存（ChromaDBにベクトル化して保存）"""
    if collection is None:
        return {"status": "error", "error": "ChromaDB not initialized"}
    
    try:
        # ユーザーIDをメタデータに含める
        metadata = {
            "importance": memory.importance,
            "category": memory.category,
            "user_id": memory.user_id,
            "timestamp": memory.timestamp,
            "source": memory.source,
            "access_count": memory.access_count,
            "last_accessed": memory.last_accessed,
            "memory_id": memory.memory_id
        }
        
        # ChromaDBに追加
        collection.add(
            documents=[memory.content],
            metadatas=[metadata],
            ids=[memory.memory_id]
        )
        
        logger.info(f"記憶作成: {memory.memory_id}")
        return {"status": "created", "memory_id": memory.memory_id}
    except Exception as e:
        logger.error(f"記憶作成失敗: {e}")
        return {"status": "error", "error": str(e)}

@app.get("/memories/{user_id}")
async def get_memories(user_id: str, category: Optional[str] = None) -> List[dict]:
    """ユーザーの記憶を取得"""
    if collection is None:
        return []
    
    try:
        # メタデータでフィルタリング
        where_clause = {"user_id": user_id}
        if category:
            where_clause["category"] = category
        
        results = collection.get(
            where=where_clause,
            include=["documents", "metadatas"]
        )
        
        memories = []
        for i in range(len(results["ids"])):
            memories.append({
                "memory_id": results["ids"][i],
                "content": results["documents"][i],
                **results["metadatas"][i]
            })
        
        return memories
    except Exception as e:
        logger.error(f"記憶取得失敗: {e}")
        return []

@app.get("/memories/search/{user_id}")
async def search_memories(user_id: str, query: str, top_k: int = 5) -> List[dict]:
    """ベクトル検索で記憶を検索"""
    if collection is None:
        return []
    
    try:
        # ユーザーIDでフィルタリングしつつベクトル検索
        results = collection.query(
            query_texts=[query],
            where={"user_id": user_id},
            n_results=top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        memories = []
        if results["ids"] and results["ids"][0]:
            for i in range(len(results["ids"][0])):
                memories.append({
                    "memory_id": results["ids"][0][i],
                    "content": results["documents"][0][i],
                    "distance": results["distances"][0][i],
                    **results["metadatas"][0][i]
                })
        
        return memories
    except Exception as e:
        logger.error(f"記憶検索失敗: {e}")
        return []

@app.put("/memories/{memory_id}/importance")
async def update_importance(memory_id: str, delta: float = 0.1) -> dict:
    """重要度を更新"""
    if collection is None:
        return {"status": "error", "error": "ChromaDB not initialized"}
    
    try:
        # 記憶を取得
        results = collection.get(
            ids=[memory_id],
            include=["metadatas"]
        )
        
        if not results["ids"]:
            return {"status": "not_found"}
        
        # メタデータを更新
        metadata = results["metadatas"][0]
        new_importance = min(1.0, max(0.0, float(metadata["importance"]) + delta))
        metadata["importance"] = new_importance
        metadata["access_count"] = int(metadata.get("access_count", 0)) + 1
        
        # 更新
        collection.update(
            ids=[memory_id],
            metadatas=[metadata]
        )
        
        return {"status": "updated", "importance": new_importance}
    except Exception as e:
        logger.error(f"重要度更新失敗: {e}")
        return {"status": "error", "error": str(e)}

@app.delete("/memories/{memory_id}")
async def delete_memory(memory_id: str) -> dict:
    """記憶を削除"""
    if collection is None:
        return {"status": "error", "error": "ChromaDB not initialized"}
    
    try:
        collection.delete(ids=[memory_id])
        return {"status": "deleted"}
    except Exception as e:
        logger.error(f"記憶削除失敗: {e}")
        return {"status": "error", "error": str(e)}

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "mem0"}
