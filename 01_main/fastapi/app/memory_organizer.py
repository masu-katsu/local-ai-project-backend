import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import httpx
import re

logger = logging.getLogger(__name__)

class MemoryOrganizer:
    """Mem0を用いた記憶整理システム"""
    
    def __init__(self, mem0_url: str = "http://mem0:8080", qwen_url: str = "http://qwen:8002"):
        self.mem0_url = mem0_url
        self.qwen_url = qwen_url
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info("MemoryOrganizer初期化完了")
    
    async def extract_important_info(
        self,
        conversation: str,
        user_id: str
    ) -> List[Dict[str, Any]]:
        """
        会話から重要情報を抽出（LLMを使用）
        
        Args:
            conversation: 会話テキスト
            user_id: ユーザーID
        
        Returns:
            抽出された重要情報のリスト
        """
        try:
            # LLMを使用して重要情報を抽出
            prompt = f"""
以下の会話から重要な情報を抽出してください。
会話: {conversation}

出力形式（JSON）:
{{
  "important_points": [
    {{"content": "重要な情報", "importance": 0.8, "category": "category_name"}},
    ...
  ]
}}

カテゴリ例: project, preference, personal, task, other
"""
            
            response = await self.client.post(
                f"{self.qwen_url}/generate",
                json={
                    "prompt": prompt,
                    "max_tokens": 512,
                    "temperature": 0.7
                }
            )
            response.raise_for_status()
            data = response.json()
            llm_response = data.get("response", "")
            
            # LLMレスポンスから重要情報を抽出
            important_points = self._parse_important_points(llm_response)
            
            if not important_points:
                # フォールバック: 簡易抽出
                important_points = self._fallback_extract(conversation)
            
            return important_points
            
        except Exception as e:
            logger.error(f"LLMによる重要情報抽出失敗: {e}")
            # フォールバック: 簡易抽出
            return self._fallback_extract(conversation)
    
    def _parse_important_points(self, llm_response: str) -> List[Dict[str, Any]]:
        """LLMレスポンスから重要情報を抽出"""
        try:
            import json
            # JSON部分を抽出
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                data = json.loads(json_match.group())
                points = data.get("important_points", [])
                # バリデーション
                validated_points = []
                for point in points:
                    if "content" in point:
                        validated_points.append({
                            "content": point["content"],
                            "importance": float(point.get("importance", 0.5)),
                            "category": point.get("category", "general")
                        })
                return validated_points
        except Exception as e:
            logger.warning(f"重要情報抽出失敗: {e}")
        
        return []
    
    def _fallback_extract(self, conversation: str) -> List[Dict[str, Any]]:
        """フォールバック: 簡易抽出"""
        important_points = []
        
        # キーワードベースの簡易抽出
        keywords = {
            "Unity": {"importance": 0.8, "category": "project"},
            "プロジェクト": {"importance": 0.7, "category": "project"},
            "好き": {"importance": 0.6, "category": "preference"},
            "嫌い": {"importance": 0.6, "category": "preference"},
            "名前": {"importance": 0.9, "category": "personal"},
            "住所": {"importance": 0.9, "category": "personal"},
            "電話": {"importance": 0.9, "category": "personal"},
            "メール": {"importance": 0.8, "category": "personal"},
            "タスク": {"importance": 0.7, "category": "task"},
            "期限": {"importance": 0.8, "category": "task"},
        }
        
        for keyword, info in keywords.items():
            if keyword in conversation:
                important_points.append({
                    "content": f"会話に「{keyword}」が含まれています",
                    "importance": info["importance"],
                    "category": info["category"]
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
        記憶を保存（Mem0 API連携）
        
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
            result = response.json()
            logger.info(f"記憶保存: {memory_id} - {content[:50]}")
            return result.get("memory_id", memory_id)
        except Exception as e:
            logger.error(f"記憶保存失敗: {e}")
            # フォールバック: ローカルに保存（Redisなど）
            return memory_id
    
    async def search_memories(
        self,
        query: str,
        user_id: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        記憶を検索（Mem0 API連携）
        
        Returns:
            関連記憶のリスト
        """
        try:
            response = await self.client.get(
                f"{self.mem0_url}/memories/search",
                params={"user_id": user_id, "query": query, "top_k": top_k}
            )
            response.raise_for_status()
            result = response.json()
            return result.get("memories", [])
        except Exception as e:
            logger.error(f"記憶検索失敗: {e}")
            return []
    
    async def update_importance(
        self,
        memory_id: str,
        delta: float = 0.1
    ) -> bool:
        """
        重要度を更新（Mem0 API連携）
        """
        try:
            response = await self.client.patch(
                f"{self.mem0_url}/memories/{memory_id}",
                json={"importance_delta": delta}
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
        ユーザーの記憶を取得（Mem0 API連携）
        """
        try:
            params = {"user_id": user_id}
            if category:
                params["category"] = category
            
            response = await self.client.get(
                f"{self.mem0_url}/memories",
                params=params
            )
            response.raise_for_status()
            result = response.json()
            return result.get("memories", [])
        except Exception as e:
            logger.error(f"ユーザー記憶取得失敗: {e}")
            return []
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
