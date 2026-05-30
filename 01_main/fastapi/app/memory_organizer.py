import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import httpx

logger = logging.getLogger(__name__)

class MemoryOrganizer:
    """Mem0を用いた記憶整理システム"""
    
    def __init__(self, mem0_url: str = "http://mem0:8080"):
        self.mem0_url = mem0_url
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info("MemoryOrganizer初期化完了")
    
    async def extract_important_info(
        self,
        conversation: str,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        会話から重要情報を抽出
        
        Args:
            conversation: 会話テキスト
            user_id: ユーザーID
        
        Returns:
            抽出された重要情報のリスト
        """
        # LLMを用いて重要情報を抽出
        # 実装はPhase2のLangGraphと統合
        important_points = []
        
        # 簡易実装（実際はLLMを使用）
        if "Unity" in conversation:
            important_points.append({
                "content": "ユーザーはUnityで開発中",
                "importance": 0.8,
                "category": "project"
            })
        
        return important_points
    
    async def save_memory(
        self,
        content: str,
        user_id: str,
        importance: float = 0.5,
        category: str = "general"
    ) -> str:
        """
        記憶を保存
        
        Returns:
            memory_id
        """
        memory_id = f"mem_{datetime.now().timestamp()}"
        
        memory = {
            "memory_id": memory_id,
            "content": content,
            "importance": importance,
            "category": category,
            "user_id": user_id,
            "timestamp": datetime.now().isoformat(),
            "source": "conversation",
            "access_count": 0,
            "last_accessed": datetime.now().isoformat()
        }
        
        # Mem0 APIに保存
        try:
            response = await self.client.post(
                f"{self.mem0_url}/memories",
                json=memory
            )
            response.raise_for_status()
            logger.info(f"記憶保存: {memory_id} - {content[:50]}")
        except Exception as e:
            logger.error(f"記憶保存失敗: {e}")
        
        return memory_id
    
    async def search_memories(
        self,
        query: str,
        user_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        記憶を検索
        
        Returns:
            関連記憶のリスト
        """
        try:
            response = await self.client.get(
                f"{self.mem0_url}/memories/search/{user_id}",
                params={"query": query, "top_k": top_k}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"記憶検索失敗: {e}")
            return []
    
    async def update_importance(
        self,
        memory_id: str,
        delta: float = 0.1
    ) -> bool:
        """
        重要度を更新
        """
        try:
            response = await self.client.put(
                f"{self.mem0_url}/memories/{memory_id}/importance",
                params={"delta": delta}
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"重要度更新失敗: {e}")
            return False
    
    async def get_user_memories(
        self,
        user_id: str,
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        ユーザーの記憶を取得
        """
        try:
            params = {}
            if category:
                params["category"] = category
            
            response = await self.client.get(
                f"{self.mem0_url}/memories/{user_id}",
                params=params
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"ユーザー記憶取得失敗: {e}")
            return []
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
