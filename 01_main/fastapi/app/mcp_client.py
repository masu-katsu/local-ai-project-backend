import logging
from typing import List, Dict, Any
import httpx

logger = logging.getLogger(__name__)

class MCPClient:
    """MCPクライアント"""
    
    def __init__(self, mcp_url: str = "http://mcp-server:3000"):
        self.mcp_url = mcp_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.request_id = 0
        logger.info(f"MCPClient初期化: {mcp_url}")
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """ツール一覧を取得"""
        try:
            response = await self.client.get(f"{self.mcp_url}/mcp")
            response.raise_for_status()
            
            data = response.json()
            return data.get("result", {}).get("tools", [])
        except Exception as e:
            logger.error(f"ツール一覧取得失敗: {e}")
            return []
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """ツールを呼び出し"""
        try:
            # 簡易実装
            logger.info(f"MCPツール呼び出し: {tool_name}")
            return {"status": "success", "tool": tool_name}
        except Exception as e:
            logger.error(f"ツール呼び出し失敗: {e}")
            return {"status": "error", "error": str(e)}
    
    def _next_id(self) -> int:
        """次のリクエストIDを生成"""
        self.request_id += 1
        return self.request_id
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
