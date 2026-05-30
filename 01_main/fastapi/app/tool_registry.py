from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
import logging
import httpx

logger = logging.getLogger(__name__)

class BaseTool(ABC):
    """ツールの基底クラス"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.description = ""
    
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]:
        """ツールを実行"""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """ツールのスキーマを取得"""
        return {
            "name": self.name,
            "description": self.description
        }

class WebSearchTool(BaseTool):
    """Web検索ツール"""
    
    def __init__(self, searxng_url: str = "http://searxng:8080"):
        super().__init__()
        self.name = "web_search"
        self.description = "Webで情報を検索します"
        self.searxng_url = searxng_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def execute(
        self,
        query: str,
        max_results: int = 5
    ) -> Dict[str, Any]:
        """Web検索を実行"""
        try:
            params = {
                "q": query,
                "format": "json",
                "engines": "google,bing"
            }
            
            response = await self.client.get(
                f"{self.searxng_url}/search",
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])[:max_results]
            
            return {
                "success": True,
                "results": results,
                "count": len(results)
            }
        except Exception as e:
            logger.error(f"Web検索失敗: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }
    
    async def close(self):
        await self.client.aclose()

class FileTool(BaseTool):
    """ファイル操作ツール"""
    
    def __init__(self, base_path: str = "/workspace"):
        super().__init__()
        self.name = "file_operations"
        self.description = "ファイルの読み書き操作を行います"
        self.base_path = base_path
    
    async def execute(
        self,
        action: str,
        path: str,
        content: Optional[str] = None
    ) -> Dict[str, Any]:
        """ファイル操作を実行"""
        import os
        
        full_path = os.path.join(self.base_path, path)
        
        try:
            if action == "read":
                with open(full_path, "r", encoding="utf-8") as f:
                    content = f.read()
                return {"success": True, "content": content}
            
            elif action == "write":
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(content)
                return {"success": True, "path": full_path}
            
            elif action == "list":
                if os.path.isdir(full_path):
                    files = os.listdir(full_path)
                    return {"success": True, "files": files}
                else:
                    return {"success": False, "error": "Not a directory"}
            
            elif action == "delete":
                os.remove(full_path)
                return {"success": True, "path": full_path}
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        
        except Exception as e:
            logger.error(f"ファイル操作失敗: {e}")
            return {"success": False, "error": str(e)}

class GitTool(BaseTool):
    """Git操作ツール"""
    
    def __init__(self, repo_path: str = "/workspace"):
        super().__init__()
        self.name = "git_operations"
        self.description = "Gitリポジトリの操作を行います"
        self.repo_path = repo_path
    
    async def execute(
        self,
        action: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Git操作を実行"""
        import subprocess
        
        try:
            if action == "status":
                result = subprocess.run(
                    ["git", "status"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True
                )
                return {"success": True, "output": result.stdout}
            
            elif action == "commit":
                message = kwargs.get("message", "Update")
                result = subprocess.run(
                    ["git", "commit", "-m", message],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True
                )
                return {"success": True, "output": result.stdout}
            
            elif action == "push":
                result = subprocess.run(
                    ["git", "push"],
                    cwd=self.repo_path,
                    capture_output=True,
                    text=True
                )
                return {"success": True, "output": result.stdout}
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        
        except Exception as e:
            logger.error(f"Git操作失敗: {e}")
            return {"success": False, "error": str(e)}

class DockerTool(BaseTool):
    """Docker操作ツール"""
    
    def __init__(self):
        super().__init__()
        self.name = "docker_operations"
        self.description = "Dockerコンテナの操作を行います"
    
    async def execute(
        self,
        action: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Docker操作を実行"""
        import subprocess
        
        try:
            if action == "ps":
                result = subprocess.run(
                    ["docker", "ps"],
                    capture_output=True,
                    text=True
                )
                return {"success": True, "output": result.stdout}
            
            elif action == "logs":
                container = kwargs.get("container")
                result = subprocess.run(
                    ["docker", "logs", container],
                    capture_output=True,
                    text=True
                )
                return {"success": True, "output": result.stdout}
            
            elif action == "restart":
                container = kwargs.get("container")
                result = subprocess.run(
                    ["docker", "restart", container],
                    capture_output=True,
                    text=True
                )
                return {"success": True, "output": result.stdout}
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        
        except Exception as e:
            logger.error(f"Docker操作失敗: {e}")
            return {"success": False, "error": str(e)}

class UnityTool(BaseTool):
    """Unity操作ツール"""
    
    def __init__(self, unity_url: str = "http://localhost:8080"):
        super().__init__()
        self.name = "unity_operations"
        self.description = "Unityとの連携操作を行います"
        self.unity_url = unity_url
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def execute(
        self,
        action: str,
        **kwargs
    ) -> Dict[str, Any]:
        """Unity操作を実行"""
        try:
            if action == "set_animation":
                animation = kwargs.get("animation")
                params = kwargs.get("params", {})
                
                response = await self.client.post(
                    f"{self.unity_url}/animation",
                    json={"animation": animation, "params": params}
                )
                response.raise_for_status()
                
                return {"success": True, "result": response.json()}
            
            elif action == "get_state":
                response = await self.client.get(f"{self.unity_url}/state")
                response.raise_for_status()
                
                return {"success": True, "state": response.json()}
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
        
        except Exception as e:
            logger.error(f"Unity操作失敗: {e}")
            return {"success": False, "error": str(e)}
    
    async def close(self):
        await self.client.aclose()

class ToolRegistry:
    """ツールレジストリ"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._register_default_tools()
    
    def _register_default_tools(self):
        """デフォルトツールを登録"""
        self.register_tool(WebSearchTool())
        self.register_tool(FileTool())
        self.register_tool(GitTool())
        self.register_tool(DockerTool())
        self.register_tool(UnityTool())
    
    def register_tool(self, tool: BaseTool):
        """ツールを登録"""
        self.tools[tool.name] = tool
        logger.info(f"ツール登録: {tool.name}")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """ツールを取得"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """ツール一覧を取得"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    async def execute_tool(
        self,
        name: str,
        **kwargs
    ) -> Dict[str, Any]:
        """ツールを実行"""
        tool = self.get_tool(name)
        if not tool:
            return {"success": False, "error": f"Tool not found: {name}"}
        
        return await tool.execute(**kwargs)
    
    async def close_all(self):
        """全ツールをクローズ"""
        for tool in self.tools.values():
            if hasattr(tool, "close"):
                await tool.close()
