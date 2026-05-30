import uuid
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class TaskPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class Subtask:
    """サブタスク"""
    
    def __init__(
        self,
        title: str,
        description: str = ""
    ):
        self.subtask_id = f"sub_{uuid.uuid4().hex[:8]}"
        self.title = title
        self.description = description
        self.status = TaskStatus.PENDING
        self.created_at = datetime.now().isoformat()
        self.completed_at = None
    
    def mark_completed(self):
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "subtask_id": self.subtask_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
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
    
    def add_subtask(self, title: str, description: str = "") -> Subtask:
        """サブタスクを追加"""
        subtask = Subtask(title, description)
        self.subtasks.append(subtask)
        self.updated_at = datetime.now().isoformat()
        return subtask
    
    def mark_in_progress(self):
        self.status = TaskStatus.IN_PROGRESS
        self.updated_at = datetime.now().isoformat()
    
    def mark_completed(self):
        self.status = TaskStatus.COMPLETED
        self.completed_at = datetime.now().isoformat()
        self.updated_at = self.completed_at
    
    def mark_failed(self):
        self.status = TaskStatus.FAILED
        self.updated_at = datetime.now().isoformat()
    
    def get_progress(self) -> float:
        """進捗率を計算"""
        if not self.subtasks:
            return 0.0
        
        completed = sum(1 for s in self.subtasks if s.status == TaskStatus.COMPLETED)
        return (completed / len(self.subtasks)) * 100
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "subtasks": [s.to_dict() for s in self.subtasks],
            "context": self.context,
            "progress": self.get_progress(),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at
        }

class TaskManager:
    """タスク管理システム"""
    
    def __init__(self):
        self.tasks: Dict[str, Task] = {}
        self.user_tasks: Dict[str, List[str]] = {}  # user_id -> task_ids
    
    def create_task(
        self,
        title: str,
        description: str,
        priority: TaskPriority = TaskPriority.MEDIUM,
        user_id: str = "default_user"
    ) -> Task:
        """タスクを作成"""
        task = Task(title, description, priority, user_id)
        self.tasks[task.task_id] = task
        
        if user_id not in self.user_tasks:
            self.user_tasks[user_id] = []
        self.user_tasks[user_id].append(task.task_id)
        
        logger.info(f"タスク作成: {task.task_id} - {title}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """タスクを取得"""
        return self.tasks.get(task_id)
    
    def get_user_tasks(
        self,
        user_id: str,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """ユーザーのタスクを取得"""
        if user_id not in self.user_tasks:
            return []
        
        task_ids = self.user_tasks[user_id]
        tasks = [self.tasks[tid] for tid in task_ids if tid in self.tasks]
        
        if status:
            tasks = [t for t in tasks if t.status == status]
        
        return tasks
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus
    ) -> bool:
        """タスクステータスを更新"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        if status == TaskStatus.IN_PROGRESS:
            task.mark_in_progress()
        elif status == TaskStatus.COMPLETED:
            task.mark_completed()
        elif status == TaskStatus.FAILED:
            task.mark_failed()
        
        logger.info(f"タスク更新: {task_id} -> {status.value}")
        return True
    
    def add_subtask(
        self,
        task_id: str,
        title: str,
        description: str = ""
    ) -> Optional[Subtask]:
        """サブタスクを追加"""
        task = self.tasks.get(task_id)
        if not task:
            return None
        
        return task.add_subtask(title, description)
    
    def complete_subtask(self, task_id: str, subtask_id: str) -> bool:
        """サブタスクを完了"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        for subtask in task.subtasks:
            if subtask.subtask_id == subtask_id:
                subtask.mark_completed()
                logger.info(f"サブタスク完了: {subtask_id}")
                return True
        
        return False
    
    def delete_task(self, task_id: str) -> bool:
        """タスクを削除"""
        task = self.tasks.get(task_id)
        if not task:
            return False
        
        user_id = task.context["user_id"]
        if user_id in self.user_tasks and task_id in self.user_tasks[user_id]:
            self.user_tasks[user_id].remove(task_id)
        
        del self.tasks[task_id]
        logger.info(f"タスク削除: {task_id}")
        return True
    
    async def analyze_task(
        self,
        message: str,
        user_id: str
    ) -> Optional[Task]:
        """
        メッセージからタスクを分析・作成
        
        簡易実装（実際はLLMを使用）
        """
        # タスクキーワード検出
        task_keywords = ["作って", "実装して", "開発して", "やって", "作成"]
        
        if any(keyword in message for keyword in task_keywords):
            # タスクを作成
            title = message[:50] + "..." if len(message) > 50 else message
            task = self.create_task(
                title=title,
                description=message,
                priority=TaskPriority.MEDIUM,
                user_id=user_id
            )
            
            # サブタスクを分解（簡易）
            task.add_subtask("要件分析", "タスクの要件を分析")
            task.add_subtask("実装", "実装を行う")
            task.add_subtask("テスト", "テストを行う")
            
            return task
        
        return None
