# Phase3 詳細設計: タスク管理とツール呼び出し

## 概要

Phase3では、Task Manager（タスク管理）とTool Calling System（ツール呼び出し）を実装する。

**目的**:
- AIに「作業能力」を持たせる（Task Manager）
- AIが外部機能を自律使用する（Tool Calling）
- Claude系のタスク管理機能を実現

---

## コンポーネント詳細

### 1. Task Manager（タスク管理）

#### 役割
- タスクの分解
- 優先順位付け
- 実行管理
- 状態管理

#### タスクデータ構造

```python
{
    "task_id": "task_001",
    "title": "README修正",
    "description": "READMEの内容を確認して修正する",
    "status": "in_progress",  # pending, in_progress, completed, failed
    "priority": "high",       # low, medium, high, critical
    "subtasks": [
        {
            "id": "st1",
            "title": "内容確認",
            "status": "completed",
            "assigned_tool": null,
            "result": "READMEの内容を確認完了"
        },
        {
            "id": "st2",
            "title": "修正文生成",
            "status": "in_progress",
            "assigned_tool": "llm",
            "result": null
        },
        {
            "id": "st3",
            "title": "Git確認",
            "status": "pending",
            "assigned_tool": "git",
            "result": null
        },
        {
            "id": "st4",
            "title": "commit提案",
            "status": "pending",
            "assigned_tool": "git",
            "result": null
        }
    ],
    "context": {
        "user_id": "player_123",
        "related_files": ["README.md"],
        "dependencies": []
    },
    "created_at": "2026-05-27T20:00:00",
    "updated_at": "2026-05-27T20:30:00",
    "completed_at": null
}
```

#### 実装

```python
# app/task_manager.py

import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)

class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"

class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Subtask:
    """サブタスク"""
    
    def __init__(
        self,
        title: str,
        assigned_tool: Optional[str] = None
    ):
        self.id = f"st_{uuid.uuid4().hex[:8]}"
        self.title = title
        self.status = TaskStatus.PENDING
        self.assigned_tool = assigned_tool
        self.result = None
        self.created_at = datetime.now().isoformat()
        self.completed_at = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "status": self.status.value,
            "assigned_tool": self.assigned_tool,
            "result": self.result,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }

class Task:
    """タスク"""
    
    def __init__(
        self,
        title: str,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        user_id: str = "default_user"
    ):
        self.task_id = f"task_{uuid.uuid4().hex[:8]}"
        self.title = title
        self.description = description
        self.status = TaskStatus.PENDING
        self.priority = priority
        self.subtasks: List[Subtask] = []
        self.context = {
            "user_id": user_id,
            "related_files": [],
            "dependencies": []
        }
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self.completed_at = None
    
    def add_subtask(self, title: str, assigned_tool: Optional[str] = None):
        """サブタスクを追加"""
        subtask = Subtask(title, assigned_tool)
        self.subtasks.append(subtask)
        self.updated_at = datetime.now().isoformat()
    
    def update_status(self, status: TaskStatus):
        """ステータスを更新"""
        self.status = status
        self.updated_at = datetime.now().isoformat()
        
        if status == TaskStatus.COMPLETED:
            self.completed_at = datetime.now().isoformat()
    
    def get_progress(self) -> float:
        """進捗を取得（0-100）"""
        if not self.subtasks:
            return 100.0 if self.status == TaskStatus.COMPLETED else 0.0
        
        completed = sum(1 for st in self.subtasks if st.status == TaskStatus.COMPLETED)
        return (completed / len(self.subtasks)) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "subtasks": [st.to_dict() for st in self.subtasks],
            "context": self.context,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "progress": self.get_progress()
        }

class TaskManager:
    """タスク管理システム"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.active_task: Optional[str] = None
        logger.info("TaskManager初期化完了")
    
    async def analyze_input(
        self,
        input_text: str,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        入力を分析してタスクか判断
        
        Returns:
            {
                "is_task": bool,
                "task_title": str,
                "task_description": str,
                "priority": str,
                "suggested_subtasks": list
            }
        """
        # 簡易実装（実際はLLMを使用）
        task_keywords = ["修正", "作成", "実装", "変更", "追加", "削除", "更新"]
        
        is_task = any(kw in input_text for kw in task_keywords)
        
        if not is_task:
            return {
                "is_task": False,
                "task_title": None,
                "task_description": None,
                "priority": None,
                "suggested_subtasks": []
            }
        
        # タスクタイトルを抽出
        task_title = input_text[:50]
        
        # 優先度を推定
        priority = self._estimate_priority(input_text)
        
        # サブタスクを提案
        suggested_subtasks = self._suggest_subtasks(input_text)
        
        return {
            "is_task": True,
            "task_title": task_title,
            "task_description": input_text,
            "priority": priority,
            "suggested_subtasks": suggested_subtasks
        }
    
    def _estimate_priority(self, text: str) -> str:
        """優先度を推定"""
        urgent_keywords = ["急ぎ", "すぐに", "重要", "critical", "urgent"]
        high_keywords = ["優先", "重要", "high"]
        
        if any(kw in text for kw in urgent_keywords):
            return TaskPriority.CRITICAL.value
        elif any(kw in text for kw in high_keywords):
            return TaskPriority.HIGH.value
        
        return TaskPriority.MEDIUM.value
    
    def _suggest_subtasks(self, text: str) -> List[Dict[str, str]]:
        """サブタスクを提案"""
        # 簡易実装（実際はLLMを使用）
        subtasks = []
        
        if "修正" in text or "変更" in text:
            subtasks.append({"title": "内容確認", "tool": null})
            subtasks.append({"title": "修正内容の生成", "tool": "llm"})
            subtasks.append({"title": "変更の適用", "tool": "file"})
        
        if "作成" in text or "実装" in text:
            subtasks.append({"title": "要件分析", "tool": "llm"})
            subtasks.append({"title": "コード生成", "tool": "llm"})
            subtasks.append({"title": "ファイル作成", "tool": "file"})
        
        return subtasks
    
    def create_task(
        self,
        title: str,
        description: str,
        priority: str = "medium",
        user_id: str = "default_user",
        subtasks: Optional[List[Dict[str, Any]]] = None
    ) -> Task:
        """タスクを作成"""
        priority_enum = TaskPriority(priority)
        task = Task(title, description, priority_enum, user_id)
        
        if subtasks:
            for st in subtasks:
                task.add_subtask(st["title"], st.get("tool"))
        
        self.tasks[task.task_id] = task
        self.active_task = task.task_id
        
        logger.info(f"タスク作成: {task.task_id} - {title}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """タスクを取得"""
        return self.tasks.get(task_id)
    
    def get_user_tasks(self, user_id: str) -> List[Task]:
        """ユーザーのタスクを取得"""
        return [
            task for task in self.tasks.values()
            if task.context["user_id"] == user_id
        ]
    
    def update_subtask_status(
        self,
        task_id: str,
        subtask_id: str,
        status: TaskStatus,
        result: Optional[str] = None
    ) -> bool:
        """サブタスクのステータスを更新"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        for subtask in task.subtasks:
            if subtask.id == subtask_id:
                subtask.status = status
                subtask.result = result
                if status == TaskStatus.COMPLETED:
                    subtask.completed_at = datetime.now().isoformat()
                
                # タスク全体のステータスを更新
                self._update_task_status(task)
                return True
        
        return False
    
    def _update_task_status(self, task: Task):
        """タスク全体のステータスを更新"""
        if not task.subtasks:
            return
        
        all_completed = all(st.status == TaskStatus.COMPLETED for st in task.subtasks)
        any_failed = any(st.status == TaskStatus.FAILED for st in task.subtasks)
        
        if any_failed:
            task.update_status(TaskStatus.FAILED)
        elif all_completed:
            task.update_status(TaskStatus.COMPLETED)
        else:
            task.update_status(TaskStatus.IN_PROGRESS)
    
    def get_active_task(self) -> Optional[Task]:
        """アクティブなタスクを取得"""
        if self.active_task:
            return self.tasks.get(self.active_task)
        return None
    
    def set_active_task(self, task_id: str) -> bool:
        """アクティブなタスクを設定"""
        if task_id in self.tasks:
            self.active_task = task_id
            return True
        return False
    
    def complete_task(self, task_id: str) -> bool:
        """タスクを完了"""
        task = self.tasks.get(task_id)
        if task:
            task.update_status(TaskStatus.COMPLETED)
            if self.active_task == task_id:
                self.active_task = None
            logger.info(f"タスク完了: {task_id}")
            return True
        return False
    
    def delete_task(self, task_id: str) -> bool:
        """タスクを削除"""
        if task_id in self.tasks:
            del self.tasks[task_id]
            if self.active_task == task_id:
                self.active_task = None
            logger.info(f"タスク削除: {task_id}")
            return True
        return False
```

---

### 2. Tool Registry（ツール登録）

#### 役割
- ツールの登録・管理
- ツールの選択
- ツールの実行

#### ツール定義

```python
# app/tools/base_tool.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BaseTool(ABC):
    """ツールの基底クラス"""
    
    def __init__(self):
        self.name = self.__class__.__name__
        self.description = self.__doc__ or ""
    
    @abstractmethod
    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        ツールを実行
        
        Returns:
            {
                "success": bool,
                "result": Any,
                "error": Optional[str]
            }
        """
        pass
    
    @abstractmethod
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """パラメータを検証"""
        pass
    
    def get_schema(self) -> Dict[str, Any]:
        """ツールのスキーマを取得"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self._get_parameters_schema()
        }
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        """パラメータスキーマ（サブクラスでオーバーライド）"""
        return {}
```

#### ツール実装

```python
# app/tools/web_search_tool.py

from app.tools.base_tool import BaseTool
import httpx
import logging

logger = logging.getLogger(__name__)

class WebSearchTool(BaseTool):
    """Web検索ツール"""
    
    def __init__(self, searxng_url: str = "http://searxng:8080"):
        super().__init__()
        self.searxng_url = searxng_url
    
    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Web検索を実行"""
        if not self.validate_params(params):
            return {
                "success": False,
                "result": None,
                "error": "Invalid parameters"
            }
        
        query = params["query"]
        max_results = params.get("max_results", 5)
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.searxng_url}/search",
                    params={
                        "q": query,
                        "format": "json",
                        "engines": "google,bing,duckduckgo"
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                
                data = response.json()
                results = data.get("results", [])[:max_results]
                
                return {
                    "success": True,
                    "result": results,
                    "error": None
                }
        except Exception as e:
            logger.error(f"Web検索エラー: {e}")
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """パラメータを検証"""
        return "query" in params and isinstance(params["query"], str)
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "query": {
                "type": "string",
                "description": "検索クエリ",
                "required": True
            },
            "max_results": {
                "type": "integer",
                "description": "最大結果数",
                "default": 5
            }
        }

# app/tools/file_tool.py

import os
import aiofiles
from app.tools.base_tool import BaseTool
import logging

logger = logging.getLogger(__name__)

class FileTool(BaseTool):
    """ファイル操作ツール"""
    
    def __init__(self, base_path: str = "/workspace"):
        super().__init__()
        self.base_path = base_path
    
    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """ファイル操作を実行"""
        if not self.validate_params(params):
            return {
                "success": False,
                "result": None,
                "error": "Invalid parameters"
            }
        
        action = params["action"]
        
        try:
            if action == "read":
                return await self._read_file(params["path"])
            elif action == "write":
                return await self._write_file(params["path"], params["content"])
            elif action == "list":
                return await self._list_directory(params.get("path", "."))
            elif action == "delete":
                return await self._delete_file(params["path"])
            else:
                return {
                    "success": False,
                    "result": None,
                    "error": f"Unknown action: {action}"
                }
        except Exception as e:
            logger.error(f"ファイル操作エラー: {e}")
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
    
    async def _read_file(self, path: str) -> Dict[str, Any]:
        """ファイルを読み込む"""
        full_path = os.path.join(self.base_path, path)
        async with aiofiles.open(full_path, mode='r', encoding='utf-8') as f:
            content = await f.read()
        return {"success": True, "result": content, "error": None}
    
    async def _write_file(self, path: str, content: str) -> Dict[str, Any]:
        """ファイルに書き込む"""
        full_path = os.path.join(self.base_path, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        async with aiofiles.open(full_path, mode='w', encoding='utf-8') as f:
            await f.write(content)
        return {"success": True, "result": f"Written to {path}", "error": None}
    
    async def _list_directory(self, path: str) -> Dict[str, Any]:
        """ディレクトリをリスト"""
        full_path = os.path.join(self.base_path, path)
        items = os.listdir(full_path)
        return {"success": True, "result": items, "error": None}
    
    async def _delete_file(self, path: str) -> Dict[str, Any]:
        """ファイルを削除"""
        full_path = os.path.join(self.base_path, path)
        os.remove(full_path)
        return {"success": True, "result": f"Deleted {path}", "error": None}
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """パラメータを検証"""
        return "action" in params
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "アクション (read/write/list/delete)",
                "required": True,
                "enum": ["read", "write", "list", "delete"]
            },
            "path": {
                "type": "string",
                "description": "ファイルパス",
                "required": True
            },
            "content": {
                "type": "string",
                "description": "ファイル内容（write時）",
                "required": False
            }
        }

# app/tools/git_tool.py

import subprocess
from app.tools.base_tool import BaseTool
import logging

logger = logging.getLogger(__name__)

class GitTool(BaseTool):
    """Git操作ツール"""
    
    def __init__(self, repo_path: str = "/workspace"):
        super().__init__()
        self.repo_path = repo_path
    
    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Git操作を実行"""
        if not self.validate_params(params):
            return {
                "success": False,
                "result": None,
                "error": "Invalid parameters"
            }
        
        action = params["action"]
        
        try:
            if action == "status":
                return await self._git_status()
            elif action == "diff":
                return await self._git_diff(params.get("file"))
            elif action == "commit":
                return await self._git_commit(params["message"])
            elif action == "log":
                return await self._git_log(params.get("max_count", 5))
            else:
                return {
                    "success": False,
                    "result": None,
                    "error": f"Unknown action: {action}"
                }
        except Exception as e:
            logger.error(f"Git操作エラー: {e}")
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
    
    async def _run_git_command(self, args: list) -> str:
        """Gitコマンドを実行"""
        result = subprocess.run(
            ["git"] + args,
            cwd=self.repo_path,
            capture_output=True,
            text=True
        )
        return result.stdout
    
    async def _git_status(self) -> Dict[str, Any]:
        """Gitステータスを取得"""
        output = await self._run_git_command(["status", "--porcelain"])
        return {"success": True, "result": output, "error": None}
    
    async def _git_diff(self, file: str = None) -> Dict[str, Any]:
        """Git diffを取得"""
        args = ["diff"]
        if file:
            args.append(file)
        output = await self._run_git_command(args)
        return {"success": True, "result": output, "error": None}
    
    async def _git_commit(self, message: str) -> Dict[str, Any]:
        """Git commitを実行"""
        await self._run_git_command(["add", "."])
        output = await self._run_git_command(["commit", "-m", message])
        return {"success": True, "result": output, "error": None}
    
    async def _git_log(self, max_count: int = 5) -> Dict[str, Any]:
        """Git logを取得"""
        output = await self._run_git_command(["log", f"-{max_count}", "--oneline"])
        return {"success": True, "result": output, "error": None}
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """パラメータを検証"""
        return "action" in params
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "アクション (status/diff/commit/log)",
                "required": True,
                "enum": ["status", "diff", "commit", "log"]
            },
            "message": {
                "type": "string",
                "description": "コミットメッセージ（commit時）",
                "required": False
            },
            "file": {
                "type": "string",
                "description": "ファイルパス（diff時）",
                "required": False
            },
            "max_count": {
                "type": "integer",
                "description": "ログ数（log時）",
                "required": False,
                "default": 5
            }
        }

# app/tools/docker_tool.py

import subprocess
from app.tools.base_tool import BaseTool
import logging

logger = logging.getLogger(__name__)

class DockerTool(BaseTool):
    """Docker操作ツール"""
    
    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Docker操作を実行"""
        if not self.validate_params(params):
            return {
                "success": False,
                "result": None,
                "error": "Invalid parameters"
            }
        
        action = params["action"]
        
        try:
            if action == "ps":
                return await self._docker_ps()
            elif action == "logs":
                return await self._docker_logs(params.get("container"))
            elif action == "restart":
                return await self._docker_restart(params.get("container"))
            else:
                return {
                    "success": False,
                    "result": None,
                    "error": f"Unknown action: {action}"
                }
        except Exception as e:
            logger.error(f"Docker操作エラー: {e}")
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
    
    async def _run_docker_command(self, args: list) -> str:
        """Dockerコマンドを実行"""
        result = subprocess.run(
            ["docker"] + args,
            capture_output=True,
            text=True
        )
        return result.stdout
    
    async def _docker_ps(self) -> Dict[str, Any]:
        """Docker psを実行"""
        output = await self._run_docker_command(["ps", "--format", "table {{.Names}}\t{{.Status}}"])
        return {"success": True, "result": output, "error": None}
    
    async def _docker_logs(self, container: str) -> Dict[str, Any]:
        """Docker logsを実行"""
        output = await self._run_docker_command(["logs", "--tail", "50", container])
        return {"success": True, "result": output, "error": None}
    
    async def _docker_restart(self, container: str) -> Dict[str, Any]:
        """Docker restartを実行"""
        output = await self._run_docker_command(["restart", container])
        return {"success": True, "result": output, "error": None}
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """パラメータを検証"""
        return "action" in params
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "アクション (ps/logs/restart)",
                "required": True,
                "enum": ["ps", "logs", "restart"]
            },
            "container": {
                "type": "string",
                "description": "コンテナ名",
                "required": False
            }
        }

# app/tools/unity_tool.py

from app.tools.base_tool import BaseTool
import logging

logger = logging.getLogger(__name__)

class UnityTool(BaseTool):
    """Unity制御ツール"""
    
    def __init__(self, unity_ws_url: str = "ws://localhost:8080"):
        super().__init__()
        self.unity_ws_url = unity_ws_url
    
    async def execute(
        self,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Unity操作を実行"""
        if not self.validate_params(params):
            return {
                "success": False,
                "result": None,
                "error": "Invalid parameters"
            }
        
        action = params["action"]
        
        try:
            if action == "set_emotion":
                return await self._set_emotion(params["emotion"])
            elif action == "play_animation":
                return await self._play_animation(params["animation"])
            elif action == "change_scene":
                return await self._change_scene(params["scene"])
            else:
                return {
                    "success": False,
                    "result": None,
                    "error": f"Unknown action: {action}"
                }
        except Exception as e:
            logger.error(f"Unity操作エラー: {e}")
            return {
                "success": False,
                "result": None,
                "error": str(e)
            }
    
    async def _set_emotion(self, emotion: str) -> Dict[str, Any]:
        """感情を設定"""
        # WebSocket経由でUnityに送信
        # 実装はWebSocketクライアントを使用
        return {"success": True, "result": f"Emotion set to {emotion}", "error": None}
    
    async def _play_animation(self, animation: str) -> Dict[str, Any]:
        """アニメーションを再生"""
        return {"success": True, "result": f"Playing {animation}", "error": None}
    
    async def _change_scene(self, scene: str) -> Dict[str, Any]:
        """シーンを変更"""
        return {"success": True, "result": f"Changed to {scene}", "error": None}
    
    def validate_params(self, params: Dict[str, Any]) -> bool:
        """パラメータを検証"""
        return "action" in params
    
    def _get_parameters_schema(self) -> Dict[str, Any]:
        return {
            "action": {
                "type": "string",
                "description": "アクション (set_emotion/play_animation/change_scene)",
                "required": True,
                "enum": ["set_emotion", "play_animation", "change_scene"]
            },
            "emotion": {
                "type": "string",
                "description": "感情（set_emotion時）",
                "required": False
            },
            "animation": {
                "type": "string",
                "description": "アニメーション名（play_animation時）",
                "required": False
            },
            "scene": {
                "type": "string",
                "description": "シーン名（change_scene時）",
                "required": False
            }
        }
```

#### Tool Registry実装

```python
# app/tool_registry.py

import logging
from typing import Dict, List, Optional, Any
from app.tools.base_tool import BaseTool
from app.tools.web_search_tool import WebSearchTool
from app.tools.file_tool import FileTool
from app.tools.git_tool import GitTool
from app.tools.docker_tool import DockerTool
from app.tools.unity_tool import UnityTool

logger = logging.getLogger(__name__)

class ToolRegistry:
    """ツールレジストリ"""
    
    def __init__(self):
        self.tools: Dict[str, BaseTool] = {}
        self._register_default_tools()
        logger.info(f"ToolRegistry初期化完了: {len(self.tools)} tools")
    
    def _register_default_tools(self):
        """デフォルトツールを登録"""
        self.register_tool("web_search", WebSearchTool())
        self.register_tool("file", FileTool())
        self.register_tool("git", GitTool())
        self.register_tool("docker", DockerTool())
        self.register_tool("unity", UnityTool())
    
    def register_tool(self, name: str, tool: BaseTool):
        """ツールを登録"""
        self.tools[name] = tool
        logger.info(f"ツール登録: {name}")
    
    def get_tool(self, name: str) -> Optional[BaseTool]:
        """ツールを取得"""
        return self.tools.get(name)
    
    def list_tools(self) -> List[Dict[str, Any]]:
        """ツール一覧を取得"""
        return [tool.get_schema() for tool in self.tools.values()]
    
    def select_tools(
        self,
        task_analysis: Dict[str, Any],
        input_message: str
    ) -> List[str]:
        """
        タスク分析に基づいてツールを選択
        
        Returns:
            ツール名のリスト
        """
        selected = []
        
        # 簡易実装（実際はLLMを使用）
        if "検索" in input_message or "search" in input_message.lower():
            selected.append("web_search")
        
        if "ファイル" in input_message or "file" in input_message.lower():
            selected.append("file")
        
        if "git" in input_message.lower() or "コミット" in input_message:
            selected.append("git")
        
        if "docker" in input_message.lower():
            selected.append("docker")
        
        if "unity" in input_message.lower() or "シーン" in input_message:
            selected.append("unity")
        
        return selected
    
    async def execute_tool(
        self,
        tool_name: str,
        params: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """ツールを実行"""
        tool = self.get_tool(tool_name)
        if not tool:
            return {
                "success": False,
                "result": None,
                "error": f"Tool not found: {tool_name}"
            }
        
        logger.info(f"ツール実行: {tool_name}")
        result = await tool.execute(params, context)
        
        return result
```

---

## FastAPIへの統合

### main.pyの更新

```python
# app/main.pyに追加

from app.task_manager import TaskManager
from app.tool_registry import ToolRegistry

# 初期化
task_manager = TaskManager()
tool_registry = ToolRegistry()

# startupイベントで初期化確認
@app.on_event("startup")
async def startup_event():
    # 既存の初期化...
    
    # Task Manager確認
    logger.info("  Task Manager: 初期化完了")
    
    # Tool Registry確認
    tools = tool_registry.list_tools()
    logger.info(f"  Tool Registry: {len(tools)} tools registered")
```

### 新規APIエンドポイント

```python
# タスク管理
@app.get("/api/tasks")
async def get_tasks(user_id: str = "default_user"):
    """ユーザーのタスクを取得"""
    tasks = task_manager.get_user_tasks(user_id)
    return {"user_id": user_id, "tasks": [t.to_dict() for t in tasks]}

@app.post("/api/tasks")
async def create_task(
    title: str,
    description: str,
    priority: str = "medium",
    user_id: str = "default_user"
):
    """タスクを作成"""
    task = task_manager.create_task(title, description, priority, user_id)
    return {"status": "created", "task": task.to_dict()}

@app.get("/api/tasks/{task_id}")
async def get_task(task_id: str):
    """タスクを取得"""
    task = task_manager.get_task(task_id)
    if task:
        return {"task": task.to_dict()}
    return {"error": "Task not found"}

@app.put("/api/tasks/{task_id}")
async def update_task(
    task_id: str,
    status: Optional[str] = None
):
    """タスクを更新"""
    task = task_manager.get_task(task_id)
    if task and status:
        from app.task_manager import TaskStatus
        task.update_status(TaskStatus(status))
        return {"status": "updated", "task": task.to_dict()}
    return {"error": "Task not found or invalid status"}

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """タスクを削除"""
    success = task_manager.delete_task(task_id)
    return {"status": "deleted" if success else "not found"}

@app.post("/api/tasks/{task_id}/subtasks/{subtask_id}")
async def update_subtask(
    task_id: str,
    subtask_id: str,
    status: str,
    result: Optional[str] = None
):
    """サブタスクを更新"""
    from app.task_manager import TaskStatus
    success = task_manager.update_subtask_status(
        task_id, subtask_id, TaskStatus(status), result
    )
    if success:
        task = task_manager.get_task(task_id)
        return {"status": "updated", "task": task.to_dict()}
    return {"error": "Subtask not found"}

# ツール管理
@app.get("/api/tools")
async def list_tools():
    """ツール一覧を取得"""
    tools = tool_registry.list_tools()
    return {"tools": tools}

@app.post("/api/tools/execute")
async def execute_tool(
    tool_name: str,
    params: dict
):
    """ツールを実行"""
    result = await tool_registry.execute_tool(tool_name, params)
    return result
```

---

## LangGraphとの統合

### graph_nodes.pyの更新

```python
# app/graph_nodes.pyのツール実行ノードを更新

async def execute_tools_node(state: AIState) -> AIState:
    """選択されたツールを実行"""
    tool_registry = ToolRegistry()
    
    tool_results = []
    for tool_name in state["selected_tools"]:
        # パラメータを推定（簡易実装）
        params = _estimate_tool_params(tool_name, state["input_message"])
        
        result = await tool_registry.execute_tool(
            tool_name,
            params,
            state
        )
        tool_results.append({
            "tool": tool_name,
            "result": result
        })
        
        # タスクマネージャーと連携
        if state.get("task_analysis", {}).get("is_task"):
            active_task = task_manager.get_active_task()
            if active_task:
                # サブタスクを更新
                for subtask in active_task.subtasks:
                    if subtask.assigned_tool == tool_name:
                        task_manager.update_subtask_status(
                            active_task.task_id,
                            subtask.id,
                            TaskStatus.COMPLETED if result["success"] else TaskStatus.FAILED,
                            str(result["result"]) if result["result"] else result["error"]
                        )
    
    state["tool_results"] = tool_results
    state["processing_steps"].append("tool_execution")
    
    return state

def _estimate_tool_params(tool_name: str, message: str) -> Dict[str, Any]:
    """ツールパラメータを推定"""
    if tool_name == "web_search":
        return {"query": message, "max_results": 5}
    elif tool_name == "file":
        return {"action": "read", "path": "README.md"}
    elif tool_name == "git":
        return {"action": "status"}
    elif tool_name == "docker":
        return {"action": "ps"}
    elif tool_name == "unity":
        return {"action": "set_emotion", "emotion": "happy"}
    return {}
```

---

## テスト計画

### ユニットテスト

```python
# tests/test_task_manager.py

import pytest
from app.task_manager import TaskManager, TaskPriority, TaskStatus

def test_create_task():
    manager = TaskManager()
    task = manager.create_task(
        title="テストタスク",
        description="テスト用",
        priority="high",
        user_id="test_user"
    )
    
    assert task.title == "テストタスク"
    assert task.priority == TaskPriority.HIGH
    assert task.status == TaskStatus.PENDING

def test_add_subtask():
    manager = TaskManager()
    task = manager.create_task("テスト", "テスト用")
    task.add_subtask("サブタスク1", "file")
    
    assert len(task.subtasks) == 1
    assert task.subtasks[0].title == "サブタスク1"

def test_task_progress():
    manager = TaskManager()
    task = manager.create_task("テスト", "テスト用")
    task.add_subtask("サブタスク1")
    task.add_subtask("サブタスク2")
    
    assert task.get_progress() == 0.0
    
    task.subtasks[0].status = TaskStatus.COMPLETED
    assert task.get_progress() == 50.0
```

### 統合テスト

```python
# tests/test_tool_registry.py

import pytest
from app.tool_registry import ToolRegistry

@pytest.mark.asyncio
async def test_tool_execution():
    registry = ToolRegistry()
    
    # ツール一覧
    tools = registry.list_tools()
    assert len(tools) > 0
    
    # ツール実行
    result = await registry.execute_tool(
        "file",
        {"action": "list", "path": "."}
    )
    
    assert result["success"] == True
```

---

## デプロイ手順

### 1. FastAPI更新

```bash
cd 01_main/fastapi
# requirements.txtに追加パッケージ（必要な場合）
# 新規モジュールを作成
# app/task_manager.py
# app/tool_registry.py
# app/tools/
#   - base_tool.py
#   - web_search_tool.py
#   - file_tool.py
#   - git_tool.py
#   - docker_tool.py
#   - unity_tool.py

# main.pyを更新
```

### 2. 再起動

```bash
docker-compose up -d fastapi
```

---

## 依存関係

```
Phase3コンポーネントの依存関係:

Task Manager
  ├─ Redis (状態保存)
  └─ LangGraph (統合)

Tool Registry
  ├─ 各種ツール
  │  ├─ WebSearchTool (SearxNG - Phase4)
  │  ├─ FileTool (ファイルシステム)
  │  ├─ GitTool (Git)
  │  ├─ DockerTool (Docker)
  │  └─ UnityTool (Unity WebSocket)
  └─ LangGraph (統合)

FastAPI main.py
  ├─ TaskManager
  └─ ToolRegistry
```

---

## 次のステップ

Phase3完了後、以下を確認:
- タスクが正しく作成・管理されているか
- ツールが正しく登録・実行されているか
- LangGraphとの統合が機能しているか
- サブタスクの進捗管理が機能しているか

確認後、Phase4（Web Search, Whisper, Piper）へ進む。
