import logging
from typing import List, Dict, Any, Optional
import httpx

logger = logging.getLogger(__name__)

class SearxNGClient:
    """SearxNGクライアント"""
    
    def __init__(self, searxng_url: str = "http://searxng:8080"):
        self.searxng_url = searxng_url
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"SearxNGClient初期化: {searxng_url}")
    
    async def search(
        self,
        query: str,
        max_results: int = 5,
        engines: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Web検索を実行
        
        Args:
            query: 検索クエリ
            max_results: 最大結果数
            engines: 使用する検索エンジン
        
        Returns:
            検索結果のリスト
        """
        try:
            params = {
                "q": query,
                "format": "json",
                "engines": ",".join(engines) if engines else "google,bing"
            }
            
            response = await self.client.get(
                f"{self.searxng_url}/search",
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])[:max_results]
            
            logger.info(f"検索完了: {query} - {len(results)}件")
            return results
            
        except Exception as e:
            logger.error(f"検索失敗: {e}")
            return []
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
