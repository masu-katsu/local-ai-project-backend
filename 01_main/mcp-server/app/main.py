from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

app = FastAPI(title="MCP Server")
logger = logging.getLogger(__name__)

class Tool(BaseModel):
    name: str
    description: str
    parameters: Dict[str, Any]

@app.get("/mcp")
async def mcp_endpoint():
    """MCPエンドポイント"""
    return {
        "jsonrpc": "2.0",
        "result": {
            "tools": [
                {
                    "name": "vscode",
                    "description": "VSCode operations",
                    "parameters": {}
                },
                {
                    "name": "github",
                    "description": "GitHub operations",
                    "parameters": {}
                },
                {
                    "name": "filesystem",
                    "description": "File system operations",
                    "parameters": {}
                }
            ]
        }
    }

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "mcp-server"}
