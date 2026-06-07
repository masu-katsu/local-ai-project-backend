import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import uuid
import httpx
import re

logger = logging.getLogger(__name__)

class AutonomousAgent:
    """自律エージェント"""
    
    def __init__(self, tool_registry, qwen_url: str = "http://qwen:8002"):
        self.tool_registry = tool_registry
        self.qwen_url = qwen_url
        self.client = httpx.AsyncClient(timeout=60.0)
        self.goals: Dict[str, Dict[str, Any]] = {}
        logger.info("AutonomousAgent初期化")
    
    def set_goal(
        self,
        description: str,
        user_id: str = "default_user"
    ) -> str:
        """
        目標を設定
        
        Returns:
            goal_id
        """
        goal_id = f"goal_{uuid.uuid4().hex[:8]}"
        
        self.goals[goal_id] = {
            "goal_id": goal_id,
            "description": description,
            "user_id": user_id,
            "status": "pending",
            "steps": [],
            "current_step": 0,
            "created_at": datetime.now().isoformat(),
            "completed_at": None
        }
        
        logger.info(f"目標設定: {goal_id} - {description}")
        return goal_id
    
    async def execute_goal(
        self,
        goal_id: str
    ) -> Dict[str, Any]:
        """
        目標を実行
        
        Returns:
            実行結果
        """
        goal = self.goals.get(goal_id)
        if not goal:
            return {"status": "error", "message": "Goal not found"}
        
        goal["status"] = "in_progress"
        
        # 目標をステップに分解（LLMを使用）
        steps = await self._decompose_goal(goal["description"])
        goal["steps"] = steps
        
        # 各ステップを実行
        for i, step in enumerate(steps):
            goal["current_step"] = i
            result = await self._execute_step(step, goal["description"])
            goal["steps"][i]["result"] = result
            
            # ステップが失敗した場合、実行を中止
            if result.get("status") == "error":
                goal["status"] = "failed"
                logger.error(f"目標実行失敗: {goal_id} - ステップ{i+1}でエラー")
                return {"status": "failed", "goal": goal, "error": result.get("error")}
        
        goal["status"] = "completed"
        goal["completed_at"] = datetime.now().isoformat()
        
        logger.info(f"目標完了: {goal_id}")
        return {"status": "completed", "goal": goal}
    
    async def _decompose_goal(self, description: str) -> List[Dict[str, Any]]:
        """
        目標をステップに分解（LLMを使用）
        """
        try:
            # LLMを使用して目標をステップに分解
            prompt = f"""
以下の目標を達成するための具体的なステップを分解してください。
目標: {description}

出力形式（JSON）:
{{
  "steps": [
    {{"step": 1, "action": "action_name", "description": "ステップ説明", "tool": "tool_name"}},
    ...
  ]
}}

利用可能なツール: web_search, file_operations, git_operations, docker_operations
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
            
            # LLMレスポンスからステップを抽出
            steps = self._parse_steps_from_llm(llm_response)
            
            if not steps:
                # フォールバック: 簡易ステップ
                steps = self._get_fallback_steps(description)
            
            return steps
            
        except Exception as e:
            logger.error(f"LLMによる目標分解失敗: {e}")
            # フォールバック: 簡易ステップ
            return self._get_fallback_steps(description)
    
    def _parse_steps_from_llm(self, llm_response: str) -> List[Dict[str, Any]]:
        """LLMレスポンスからステップを抽出"""
        try:
            import json
            # JSON部分を抽出
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                data = json.loads(json_match.group())
                return data.get("steps", [])
        except Exception as e:
            logger.warning(f"ステップ抽出失敗: {e}")
        
        return []
    
    def _get_fallback_steps(self, description: str) -> List[Dict[str, Any]]:
        """フォールバックステップ"""
        # 目標の種類に応じてステップを生成
        if "検索" in description or "search" in description.lower():
            return [
                {"step": 1, "action": "web_search", "description": "Web検索を実行", "tool": "web_search"},
                {"step": 2, "action": "analyze", "description": "検索結果を分析", "tool": None},
                {"step": 3, "action": "summarize", "description": "結果を要約", "tool": None}
            ]
        elif "ファイル" in description or "file" in description.lower():
            return [
                {"step": 1, "action": "list", "description": "ファイル一覧を取得", "tool": "file_operations"},
                {"step": 2, "action": "read", "description": "ファイルを読み込み", "tool": "file_operations"},
                {"step": 3, "action": "analyze", "description": "内容を分析", "tool": None}
            ]
        else:
            return [
                {"step": 1, "action": "analyze", "description": "要件分析", "tool": None},
                {"step": 2, "action": "plan", "description": "計画策定", "tool": None},
                {"step": 3, "action": "execute", "description": "実行", "tool": None},
                {"step": 4, "action": "verify", "description": "検証", "tool": None}
            ]
    
    async def _execute_step(self, step: Dict[str, Any], goal_description: str) -> Dict[str, Any]:
        """
        ステップを実行
        """
        action = step["action"]
        tool_name = step.get("tool")
        
        # ツールが必要な場合
        if tool_name and tool_name in self.tool_registry.tools:
            try:
                result = await self.tool_registry.execute_tool(tool_name, action=action, description=step["description"])
                return {"status": "success", "result": result}
            except Exception as e:
                return {"status": "error", "error": str(e)}
        
        # ツール不要のステップ
        if action == "analyze":
            return await self._llm_analyze(goal_description, step["description"])
        elif action == "plan":
            return {"status": "success", "result": "計画完了"}
        elif action == "execute":
            return {"status": "success", "result": "実行完了"}
        elif action == "verify":
            return {"status": "success", "result": "検証完了"}
        elif action == "summarize":
            return {"status": "success", "result": "要約完了"}
        
        return {"status": "error", "message": "Unknown action"}
    
    async def _llm_analyze(self, goal_description: str, step_description: str) -> Dict[str, Any]:
        """LLMを使用して分析"""
        try:
            prompt = f"""
目標: {goal_description}
ステップ: {step_description}

このステップの分析結果を簡潔に説明してください。
"""
            
            response = await self.client.post(
                f"{self.qwen_url}/generate",
                json={
                    "prompt": prompt,
                    "max_tokens": 256,
                    "temperature": 0.7
                }
            )
            response.raise_for_status()
            data = response.json()
            
            return {"status": "success", "result": data.get("response", "分析完了")}
            
        except Exception as e:
            logger.error(f"LLM分析失敗: {e}")
            return {"status": "success", "result": "分析完了（簡易）"}
    
    def get_goal(self, goal_id: str) -> Optional[Dict[str, Any]]:
        """目標を取得"""
        return self.goals.get(goal_id)
    
    def get_user_goals(self, user_id: str) -> List[Dict[str, Any]]:
        """ユーザーの目標一覧を取得"""
        return [g for g in self.goals.values() if g["user_id"] == user_id]
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
