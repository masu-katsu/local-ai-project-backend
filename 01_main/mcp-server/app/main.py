from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import json

app = FastAPI(title="MCP Server")
logger = logging.getLogger(__name__)

class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]

class ToolCallRequest(BaseModel):
    tool_name: str
    arguments: Dict[str, Any]

class ToolCallResponse(BaseModel):
    result: Any
    error: Optional[str] = None

# ツール定義
AVAILABLE_TOOLS = {
    "vscode": {
        "name": "vscode",
        "description": "VSCode operations - open file, get cursor position, etc.",
        "parameters": {
            "action": {"type": "string", "enum": ["open_file", "get_cursor", "set_cursor"]},
            "file_path": {"type": "string"},
            "line": {"type": "integer"},
            "column": {"type": "integer"}
        }
    },
    "github": {
        "name": "github",
        "description": "GitHub operations - get repo info, create issue, etc.",
        "parameters": {
            "action": {"type": "string", "enum": ["get_repo", "create_issue", "get_issues"]},
            "repo": {"type": "string"},
            "title": {"type": "string"},
            "body": {"type": "string"}
        }
    },
    "filesystem": {
        "name": "filesystem",
        "description": "File system operations - read, write, list files",
        "parameters": {
            "action": {"type": "string", "enum": ["read", "write", "list", "delete"]},
            "path": {"type": "string"},
            "content": {"type": "string"}
        }
    },
    "web_search": {
        "name": "web_search",
        "description": "Web search operations",
        "parameters": {
            "query": {"type": "string"},
            "max_results": {"type": "integer", "default": 5}
        }
    }
}

@app.get("/mcp")
async def mcp_endpoint():
    """MCPプロトコル準拠のツール一覧エンドポイント"""
    return {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": {
                        "type": "object",
                        "properties": tool["parameters"]
                    }
                }
                for tool in AVAILABLE_TOOLS.values()
            ]
        }
    }

@app.post("/mcp/call")
async def call_tool(request: ToolCallRequest) -> ToolCallResponse:
    """ツールを呼び出す（MCPプロトコル準拠）"""
    tool_name = request.tool_name
    arguments = request.arguments
    
    if tool_name not in AVAILABLE_TOOLS:
        return ToolCallResponse(
            result=None,
            error=f"Tool not found: {tool_name}"
        )
    
    try:
        # ツール実行ロジック
        result = await _execute_tool(tool_name, arguments)
        return ToolCallResponse(result=result)
    except Exception as e:
        logger.error(f"ツール実行失敗: {e}")
        return ToolCallResponse(
            result=None,
            error=str(e)
        )

async def _execute_tool(tool_name: str, arguments: Dict[str, Any]) -> Any:
    """ツールを実行"""
    action = arguments.get("action", "")
    
    if tool_name == "filesystem":
        return await _execute_filesystem(action, arguments)
    elif tool_name == "vscode":
        return await _execute_vscode(action, arguments)
    elif tool_name == "github":
        return await _execute_github(action, arguments)
    elif tool_name == "web_search":
        return await _execute_web_search(arguments)
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

async def _execute_filesystem(action: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """ファイルシステム操作を実行"""
    import os
    
    path = arguments.get("path", "")
    
    if action == "read":
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    elif action == "write":
        content = arguments.get("content", "")
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    elif action == "list":
        try:
            if os.path.isdir(path):
                files = os.listdir(path)
                return {"success": True, "files": files}
            else:
                return {"success": False, "error": "Not a directory"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    elif action == "delete":
        try:
            os.remove(path)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    else:
        return {"success": False, "error": f"Unknown action: {action}"}

async def _execute_vscode(action: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """VSCode操作を実行（簡易実装）"""
    # 実際のVSCode拡張APIとの連携が必要
    return {
        "success": True,
        "action": action,
        "message": f"VSCode {action} executed (simplified implementation)"
    }

async def _execute_github(action: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """GitHub操作を実行（簡易実装）"""
    # 実際のGitHub APIとの連携が必要
    return {
        "success": True,
        "action": action,
        "message": f"GitHub {action} executed (simplified implementation)"
    }

async def _execute_web_search(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Web検索を実行（簡易実装）"""
    # 実際の検索エンジンとの連携が必要
    query = arguments.get("query", "")
    return {
        "success": True,
        "query": query,
        "results": [
            {"title": "Result 1", "url": "https://example.com/1"},
            {"title": "Result 2", "url": "https://example.com/2"}
        ]
    }

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "service": "mcp-server",
        "tools_count": len(AVAILABLE_TOOLS)
    }
