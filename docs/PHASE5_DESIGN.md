# Phase5 詳細設計: 高度な拡張

## 概要

Phase5では、MCP（Model Context Protocol）、Vision（画像認識）、自律Agentを実装する。

**目的**:
- AI外部ツール共通規格（MCP）
- 画像認識機能（Vision）
- 自律エージェント化

---

## コンポーネント詳細

### 1. MCP（Model Context Protocol）

#### 役割
- AI外部ツール共通規格
- 標準化されたツール連携
- 将来の拡張性確保

#### 対応ツール
- VSCode
- GitHub
- Browser
- FileSystem
- Unity

#### MCPサーバー実装

```python
# mcp-server/app/main.py

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

app = FastAPI(title="MCP Server")
logger = logging.getLogger(__name__)

class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: str
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None

# ツール定義
MCP_TOOLS = {
    "vscode_read_file": {
        "name": "vscode_read_file",
        "description": "VSCodeでファイルを読み込む",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "ファイルパス"}
            },
            "required": ["path"]
        }
    },
    "github_search_repos": {
        "name": "github_search_repos",
        "description": "GitHubでリポジトリを検索",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "検索クエリ"}
            },
            "required": ["query"]
        }
    },
    "browser_navigate": {
        "name": "browser_navigate",
        "description": "ブラウザでURLを開く",
        "inputSchema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL"}
            },
            "required": ["url"]
        }
    },
    "filesystem_list": {
        "name": "filesystem_list",
        "description": "ファイルシステムをリスト",
        "inputSchema": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "パス"}
            },
            "required": ["path"]
        }
    },
    "unity_send_command": {
        "name": "unity_send_command",
        "description": "Unityにコマンドを送信",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "コマンド"},
                "params": {"type": "object", "description": "パラメータ"}
            },
            "required": ["command"]
        }
    }
}

@app.post("/mcp")
async def handle_mcp(request: MCPRequest) -> MCPResponse:
    """MCPリクエストを処理"""
    logger.info(f"MCPリクエスト: {request.method}")
    
    try:
        if request.method == "tools/list":
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                result={
                    "tools": list(MCP_TOOLS.values())
                }
            )
        
        elif request.method == "tools/call":
            tool_name = request.params.get("name")
            tool_args = request.params.get("arguments", {})
            
            result = await execute_tool(tool_name, tool_args)
            
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                result={"content": [{"type": "text", "text": str(result)}]}
            )
        
        else:
            return MCPResponse(
                jsonrpc="2.0",
                id=request.id,
                error={"code": -32601, "message": "Method not found"}
            )
    
    except Exception as e:
        logger.error(f"MCPエラー: {e}")
        return MCPResponse(
            jsonrpc="2.0",
            id=request.id,
            error={"code": -32603, "message": str(e)}
        )

async def execute_tool(tool_name: str, args: Dict[str, Any]) -> Any:
    """ツールを実行"""
    # 実装は各ツールに応じて
    if tool_name == "vscode_read_file":
        return f"Reading file: {args.get('path')}"
    elif tool_name == "github_search_repos":
        return f"Searching GitHub: {args.get('query')}"
    elif tool_name == "browser_navigate":
        return f"Navigating to: {args.get('url')}"
    elif tool_name == "filesystem_list":
        return f"Listing: {args.get('path')}"
    elif tool_name == "unity_send_command":
        return f"Sending Unity command: {args.get('command')}"
    else:
        raise ValueError(f"Unknown tool: {tool_name}")

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "ok", "tools": len(MCP_TOOLS)}
```

#### MCP Dockerfile

```dockerfile
# mcp-server/Dockerfile

FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3000"]
```

#### MCP requirements.txt

```
fastapi==0.115.0
uvicorn==0.30.0
pydantic==2.9.0
```

#### MCPクライアント実装

```python
# app/mcp_client.py

import logging
import httpx
from typing import Dict, Any, List, Optional

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
        payload = {
            "jsonrpc": "2.0",
            "id": str(self._next_id()),
            "method": "tools/list"
        }
        
        response = await self.client.post(f"{self.mcp_url}/mcp", json=payload)
        response.raise_for_status()
        
        data = response.json()
        return data.get("result", {}).get("tools", [])
    
    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> Any:
        """ツールを呼び出し"""
        payload = {
            "jsonrpc": "2.0",
            "id": str(self._next_id()),
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            }
        }
        
        response = await self.client.post(f"{self.mcp_url}/mcp", json=payload)
        response.raise_for_status()
        
        data = response.json()
        
        if "error" in data:
            raise Exception(data["error"]["message"])
        
        return data.get("result")
    
    def _next_id(self) -> int:
        """次のリクエストIDを生成"""
        self.request_id += 1
        return self.request_id
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
```

---

### 2. Vision（画像認識）

#### 役割
- 画像認識
- 画像からの情報抽出
- マルチモーダル対応

#### 実装

```python
# app/vision_processor.py

import logging
import base64
from typing import Optional, Dict, Any
from PIL import Image
import io

logger = logging.getLogger(__name__)

class VisionProcessor:
    """画像処理システム"""
    
    def __init__(self):
        # Visionモデルの初期化（実際はCLIPやBLIPなどを使用）
        logger.info("VisionProcessor初期化完了")
    
    def decode_image(self, image_data: bytes) -> Optional[Image.Image]:
        """画像データをデコード"""
        try:
            image = Image.open(io.BytesIO(image_data))
            return image
        except Exception as e:
            logger.error(f"画像デコードエラー: {e}")
            return None
    
    def encode_image(self, image: Image.Image, format: str = "PNG") -> bytes:
        """画像をエンコード"""
        buffer = io.BytesIO()
        image.save(buffer, format=format)
        return buffer.getvalue()
    
    def analyze_image(
        self,
        image_data: bytes,
        query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        画像を分析
        
        Args:
            image_data: 画像データ
            query: 分析クエリ（オプション）
        
        Returns:
            分析結果
        """
        image = self.decode_image(image_data)
        if not image:
            return {"error": "Invalid image data"}
        
        # 簡易実装（実際はVisionモデルを使用）
        width, height = image.size
        mode = image.mode
        
        result = {
            "width": width,
            "height": height,
            "mode": mode,
            "format": image.format,
            "description": f"{width}x{height} {mode} image"
        }
        
        if query:
            result["query_response"] = f"Query: {query}"
        
        logger.info(f"画像分析完了: {width}x{height}")
        return result
    
    def extract_text_from_image(self, image_data: bytes) -> str:
        """画像からテキストを抽出（OCR）"""
        # 簡易実装（実際はTesseractなどを使用）
        image = self.decode_image(image_data)
        if not image:
            return ""
        
        # 実際のOCR実装はここに
        return "OCR結果（プレースホルダー）"
    
    def detect_objects(self, image_data: bytes) -> List[Dict[str, Any]]:
        """画像内の物体を検出"""
        # 簡易実装（実際はYOLOなどを使用）
        return [
            {"label": "object1", "confidence": 0.9, "bbox": [10, 10, 100, 100]}
        ]
```

#### Vision APIエンドポイント

```python
# app/main.pyに追加

from app.vision_processor import VisionProcessor

# 初期化
vision_processor = VisionProcessor()

@app.post("/api/vision/analyze")
async def analyze_image(
    image: UploadFile = File(...),
    query: Optional[str] = None
):
    """画像を分析"""
    image_data = await image.read()
    result = vision_processor.analyze_image(image_data, query)
    return result

@app.post("/api/vision/ocr")
async def extract_text(image: UploadFile = File(...)):
    """画像からテキストを抽出"""
    image_data = await image.read()
    text = vision_processor.extract_text_from_image(image_data)
    return {"text": text}

@app.post("/api/vision/detect")
async def detect_objects(image: UploadFile = File(...)):
    """画像内の物体を検出"""
    image_data = await image.read()
    objects = vision_processor.detect_objects(image_data)
    return {"objects": objects}
```

---

### 3. 自律Agent

#### 役割
- 自律的なタスク実行
- 目標指向の行動
- 自己改善

#### 実装

```python
# app/autonomous_agent.py

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

class AutonomousAgent:
    """自律エージェント"""
    
    def __init__(
        self,
        task_manager,
        tool_registry,
        langgraph_orchestrator
    ):
        self.task_manager = task_manager
        self.tool_registry = tool_registry
        self.langgraph_orchestrator = langgraph_orchestrator
        self.goals: List[Dict[str, Any]] = []
        self.is_running = False
        logger.info("AutonomousAgent初期化完了")
    
    def set_goal(
        self,
        goal: str,
        priority: str = "medium",
        deadline: Optional[str] = None
    ):
        """目標を設定"""
        goal_id = f"goal_{datetime.now().timestamp()}"
        
        self.goals.append({
            "goal_id": goal_id,
            "goal": goal,
            "priority": priority,
            "deadline": deadline,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "progress": 0.0
        })
        
        logger.info(f"目標設定: {goal}")
        return goal_id
    
    async def start(self):
        """自律実行を開始"""
        self.is_running = True
        logger.info("自律エージェント起動")
        
        while self.is_running:
            await self.process_goals()
            await asyncio.sleep(10)  # 10秒ごとにチェック
    
    async def stop(self):
        """自律実行を停止"""
        self.is_running = False
        logger.info("自律エージェント停止")
    
    async def process_goals(self):
        """目標を処理"""
        for goal in self.goals:
            if goal["status"] == "pending":
                await self.execute_goal(goal)
            elif goal["status"] == "in_progress":
                await self.monitor_goal(goal)
    
    async def execute_goal(self, goal: Dict[str, Any]):
        """目標を実行"""
        logger.info(f"目標実行開始: {goal['goal']}")
        goal["status"] = "in_progress"
        
        # 目標をタスクに分解
        task_analysis = await self.task_manager.analyze_input(
            goal["goal"],
            context={}
        )
        
        if task_analysis["is_task"]:
            # タスクを作成
            task = self.task_manager.create_task(
                title=task_analysis["task_title"],
                description=task_analysis["task_description"],
                priority=task_analysis["priority"],
                user_id="autonomous_agent"
            )
            
            # サブタスクを追加
            for st in task_analysis["suggested_subtasks"]:
                task.add_subtask(st["title"], st.get("tool"))
            
            # サブタスクを実行
            for subtask in task.subtasks:
                if subtask.assigned_tool:
                    # ツールを実行
                    params = self._estimate_tool_params(subtask.assigned_tool, goal["goal"])
                    result = await self.tool_registry.execute_tool(
                        subtask.assigned_tool,
                        params
                    )
                    
                    # サブタスクを更新
                    self.task_manager.update_subtask_status(
                        task.task_id,
                        subtask.id,
                        "completed" if result["success"] else "failed",
                        str(result["result"]) if result["result"] else result["error"]
                    )
            
            # タスクを完了
            self.task_manager.complete_task(task.task_id)
            goal["status"] = "completed"
            goal["progress"] = 100.0
            logger.info(f"目標完了: {goal['goal']}")
    
    async def monitor_goal(self, goal: Dict[str, Any]):
        """目標を監視"""
        # 進捗を更新
        # 実装はタスクの進捗に基づいて
        pass
    
    def _estimate_tool_params(self, tool_name: str, goal: str) -> Dict[str, Any]:
        """ツールパラメータを推定"""
        if tool_name == "web_search":
            return {"query": goal, "max_results": 5}
        elif tool_name == "file":
            return {"action": "list", "path": "."}
        elif tool_name == "git":
            return {"action": "status"}
        return {}
    
    def get_goals(self) -> List[Dict[str, Any]]:
        """目標一覧を取得"""
        return self.goals
    
    def get_goal_status(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """目標の状態を取得"""
        for goal in self.goals:
            if goal["goal_id"] == goal_id:
                return goal
        return None
```

#### Agent APIエンドポイント

```python
# app/main.pyに追加

from app.autonomous_agent import AutonomousAgent

# 初期化
autonomous_agent = AutonomousAgent(
    task_manager=task_manager,
    tool_registry=tool_registry,
    langgraph_orchestrator=langgraph_orchestrator
)

# バックグラウンドでエージェントを実行
@app.on_event("startup")
async def start_agent():
    asyncio.create_task(autonomous_agent.start())

@app.on_event("shutdown")
async def stop_agent():
    await autonomous_agent.stop()

@app.post("/api/agent/goals")
async def set_goal(
    goal: str,
    priority: str = "medium",
    deadline: Optional[str] = None
):
    """目標を設定"""
    goal_id = autonomous_agent.set_goal(goal, priority, deadline)
    return {"goal_id": goal_id, "status": "set"}

@app.get("/api/agent/goals")
async def get_goals():
    """目標一覧を取得"""
    return {"goals": autonomous_agent.get_goals()}

@app.get("/api/agent/goals/{goal_id}")
async def get_goal_status(goal_id: str):
    """目標の状態を取得"""
    goal = autonomous_agent.get_goal_status(goal_id)
    if goal:
        return goal
    return {"error": "Goal not found"}

@app.post("/api/agent/start")
async def start_agent():
    """エージェントを開始"""
    asyncio.create_task(autonomous_agent.start())
    return {"status": "started"}

@app.post("/api/agent/stop")
async def stop_agent():
    """エージェントを停止"""
    await autonomous_agent.stop()
    return {"status": "stopped"}
```

---

## Docker設定

```yaml
# docker-compose.ymlに追加

mcp-server:
  build: ./mcp-server
  container_name: ai-mcp-server
  ports:
    - "3000:3000"
  networks:
    - backend
  restart: unless-stopped
```

---

## FastAPIへの統合

### main.pyの更新

```python
# app/main.pyに追加

from app.mcp_client import MCPClient
from app.vision_processor import VisionProcessor
from app.autonomous_agent import AutonomousAgent

# 環境変数追加
MCP_URL = os.getenv("MCP_URL", "http://mcp-server:3000")

# 初期化
mcp_client = MCPClient(mcp_url=MCP_URL)
vision_processor = VisionProcessor()
autonomous_agent = AutonomousAgent(
    task_manager=task_manager,
    tool_registry=tool_registry,
    langgraph_orchestrator=langgraph_orchestrator
)

# startupイベントで初期化確認
@app.on_event("startup")
async def startup_event():
    # 既存の初期化...
    
    # MCP確認
    logger.info(f"  MCP: {MCP_URL}")
    
    # Vision確認
    logger.info("  Vision: 初期化完了")
    
    # Agent確認
    logger.info("  Autonomous Agent: 初期化完了")
    
    # エージェントをバックグラウンドで実行
    asyncio.create_task(autonomous_agent.start())
```

### MCP Tool Registryへの統合

```python
# app/tool_registry.pyに追加

from app.mcp_client import MCPClient

class ToolRegistry:
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._register_default_tools()
        self.mcp_client = MCPClient()
        self._register_mcp_tools()
    
    async def _register_mcp_tools(self):
        """MCPツールを登録"""
        try:
            mcp_tools = await self.mcp_client.list_tools()
            
            for tool in mcp_tools:
                # MCPツール用のラッパーを作成
                wrapper = MCPToolWrapper(tool, self.mcp_client)
                self.register_tool(tool["name"], wrapper)
            
            logger.info(f"MCPツール登録: {len(mcp_tools)} tools")
        except Exception as e:
            logger.warning(f"MCPツール登録失敗: {e}")

class MCPToolWrapper(BaseTool):
    """MCPツールのラッパー"""
    
    def __init__(self, tool_schema: Dict[str, Any], mcp_client: MCPClient):
        super().__init__()
        self.tool_schema = tool_schema
        self.mcp_client = mcp_client
        self.name = tool_schema["name"]
        self.description = tool_schema["description"]
    
    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """MCPツールを実行"""
        try:
            result = await self.mcp_client.call_tool(self.name, params)
            return {
                "success": True,
                "result": result,
                "error": None
            }
        except Exception as e:
            logger.error(f"MCPツール実行エラー: {e}")
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """パラメータを検証"""
        # MCPのスキーマに基づいて検証
        return True
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        return self.tool_schema.get("inputSchema", {})
```

---

## テスト計画

### ユニットテスト

```python
# tests/test_mcp_client.py

import pytest
from app.mcp_client import MCPClient

@pytest.mark.asyncio
async def test_mcp_list_tools():
    client = MCPClient()
    tools = await client.list_tools()
    assert len(tools) > 0

@pytest.mark.asyncio
async def test_mcp_call_tool():
    client = MCPClient()
    result = await client.call_tool("filesystem_list", {"path": "."})
    assert result is not None
```

### 統合テスト

```python
# tests/test_autonomous_agent.py

import pytest
from app.autonomous_agent import AutonomousAgent

@pytest.mark.asyncio
async def test_agent_goal_execution():
    agent = AutonomousAgent(task_manager, tool_registry, langgraph_orchestrator)
    
    goal_id = agent.set_goal("READMEを確認して修正する", priority="high")
    
    # 目標を処理
    await agent.execute_goal(agent.get_goal_status(goal_id))
    
    goal = agent.get_goal_status(goal_id)
    assert goal["status"] == "completed"
```

---

## デプロイ手順

### 1. MCPサーバー構築

```bash
cd 01_main
mkdir -p mcp-server/app
# Dockerfile, requirements.txt, main.pyを作成
docker-compose build mcp-server
docker-compose up -d mcp-server
```

### 2. FastAPI更新

```bash
cd fastapi
# requirements.txtに追加
# 新規モジュールを作成
# app/mcp_client.py
# app/vision_processor.py
# app/autonomous_agent.py

# main.pyを更新
# app/tool_registry.pyを更新
```

### 3. 環境変数設定

```bash
# .envに追加
MCP_URL=http://mcp-server:3000
```

### 4. 再起動

```bash
docker-compose up -d fastapi
```

---

## 依存関係

```
Phase5コンポーネントの依存関係:

MCP
  ├─ MCP Server
  ├─ MCP Client
  └─ Tool Registry (MCPツール統合)

Vision
  ├─ Vision Processor
  └─ FastAPI (APIエンドポイント)

Autonomous Agent
  ├─ Task Manager (Phase3)
  ├─ Tool Registry (Phase3)
  ├─ LangGraph (Phase2)
  └─ FastAPI (APIエンドポイント)

FastAPI main.py
  ├─ MCPClient
  ├─ VisionProcessor
  └─ AutonomousAgent
```

---

## セキュリティ考慮

### MCP認証
- MCPサーバーへのアクセスは内部ネットワークのみ
- トークン認証の実装（オプション）

### Vision処理
- 画像サイズの制限
- サポートされるフォーマットの制限
- 悪意ある画像のフィルタリング

### Agent制限
- 実行可能なツールの制限
- 目標の承認フロー（オプション）
- 実行時間の制限

---

## 次のステップ

Phase5完了後、以下を確認:
- MCPサーバーが正常に動作しているか
- MCPツールが正しく登録・実行されているか
- Vision処理が機能しているか
- 自律エージェントが目標を実行できているか

全Phase完了後、システム全体の統合テストを実施する。
