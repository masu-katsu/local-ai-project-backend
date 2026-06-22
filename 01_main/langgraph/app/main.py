from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, TypedDict, Annotated
import logging
import operator
import os
import re
import json
from langgraph.graph import StateGraph, END
import httpx

app = FastAPI(title="LangGraph Service")
logger = logging.getLogger(__name__)

# 状態定義
class AgentState(TypedDict):
    user_id: str
    input_message: str
    emotion: Dict[str, Any]
    short_term_context: Dict[str, Any]
    long_term_context: List[str]
    important_memories: List[Dict[str, Any]]
    task_analysis_result: Dict[str, Any]
    selected_tools: List[str]
    llm_response: str
    final_response: str
    processing_steps: List[str]

# LangGraphグラフ構築
class LangGraphProcessor:
    def __init__(self):
        self.phi3_url = os.getenv("PHI3_URL", "http://phi3:8001")
        self.qwen_url = os.getenv("QWEN_URL", "http://qwen:8002")
        self.client = httpx.AsyncClient(timeout=60.0)
        
        # グラフを構築
        self.graph = self._build_graph()
        logger.info("LangGraphグラフ構築完了")
    
    def _build_graph(self) -> StateGraph:
        """LangGraphの処理フローを構築"""
        workflow = StateGraph(AgentState)
        
        # ノードを追加（状態キーと重複しない名前を使用）
        workflow.add_node("node_emotion_update", self._emotion_update)
        workflow.add_node("node_memory_search", self._memory_search)
        workflow.add_node("node_task_analysis", self._task_analysis)
        workflow.add_node("node_tool_selection", self._tool_selection)
        workflow.add_node("node_llm_inference", self._llm_inference)
        workflow.add_node("node_memory_save", self._memory_save)
        workflow.add_node("node_final_response", self._final_response)
        
        # エッジを定義（線形フロー）
        workflow.set_entry_point("node_emotion_update")
        workflow.add_edge("node_emotion_update", "node_memory_search")
        workflow.add_edge("node_memory_search", "node_task_analysis")
        workflow.add_edge("node_task_analysis", "node_tool_selection")
        workflow.add_edge("node_tool_selection", "node_llm_inference")
        workflow.add_edge("node_llm_inference", "node_memory_save")
        workflow.add_edge("node_memory_save", "node_final_response")
        workflow.add_edge("node_final_response", END)
        
        return workflow.compile()
    
    async def _emotion_update(self, state: AgentState) -> AgentState:
        """感情を更新（LLMベース）"""
        state["processing_steps"].append("emotion_update")
        try:
            # LLMを使用して感情を分析
            prompt = f"""
以下のメッセージから感情を分析してください。JSON形式で出力してください。

メッセージ: {state["input_message"]}

出力形式:
{{
  "mood": "happy|sad|excited|curious|neutral|angry|anxious",
  "energy": 0-100の整数,
  "confidence": 0.0-1.0の小数
}}
"""
            response = await self.client.post(
                f"{self.phi3_url}/generate",
                json={"prompt": prompt, "max_tokens": 256, "temperature": 0.3}
            )
            response.raise_for_status()
            data = response.json()
            llm_response = data.get("response", "")
            
            # JSONをパース
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                emotion_data = json.loads(json_match.group())
                state["emotion"] = {
                    "mood": emotion_data.get("mood", "neutral"),
                    "energy": emotion_data.get("energy", 50),
                    "confidence": emotion_data.get("confidence", 0.7)
                }
            else:
                state["emotion"] = {"mood": "neutral", "energy": 50, "confidence": 0.5}
        except Exception as e:
            logger.warning(f"感情更新失敗: {e}")
            state["emotion"] = {"mood": "neutral", "energy": 50, "confidence": 0.5}
        return state
    
    async def _memory_search(self, state: AgentState) -> AgentState:
        """記憶を検索（実際のサービス連携）"""
        state["processing_steps"].append("memory_search")
        try:
            # Mem0 APIを呼び出して記憶を検索
            mem0_url = os.getenv("MEM0_URL", "http://mem0:8080")
            response = await self.client.get(
                f"{mem0_url}/memories/{state['user_id']}",
                params={"query": state["input_message"], "top_k": 3}
            )
            response.raise_for_status()
            memories = response.json()
            
            # 記憶をコンテキストに変換
            state["long_term_context"] = [
                mem.get("content", "") for mem in memories if mem.get("content")
            ]
            logger.info(f"記憶検索: {len(state['long_term_context'])}件")
        except Exception as e:
            logger.warning(f"記憶検索失敗: {e}")
            state["long_term_context"] = []
        return state
    
    async def _task_analysis(self, state: AgentState) -> AgentState:
        """タスクを分析（LLMベース）"""
        state["processing_steps"].append("task_analysis")
        try:
            # LLMを使用してタスクを分析
            prompt = f"""
以下のメッセージからタスクを分析してください。JSON形式で出力してください。

メッセージ: {state["input_message"]}

出力形式:
{{
  "is_task": true/false,
  "task_type": "string",
  "priority": "low|medium|high|urgent"
}}
"""
            response = await self.client.post(
                f"{self.phi3_url}/generate",
                json={"prompt": prompt, "max_tokens": 256, "temperature": 0.3}
            )
            response.raise_for_status()
            data = response.json()
            llm_response = data.get("response", "")
            
            # JSONをパース
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                task_data = json.loads(json_match.group())
                state["task_analysis_result"] = {
                    "is_task": task_data.get("is_task", False),
                    "task_type": task_data.get("task_type", None),
                    "priority": task_data.get("priority", "medium")
                }
            else:
                state["task_analysis_result"] = {"is_task": False, "task_type": None, "priority": "medium"}
        except Exception as e:
            logger.warning(f"タスク分析失敗: {e}")
            state["task_analysis_result"] = {"is_task": False, "task_type": None, "priority": "medium"}
        return state
    
    async def _tool_selection(self, state: AgentState) -> AgentState:
        """ツールを選択（LLMベース）"""
        state["processing_steps"].append("tool_selection")
        try:
            # LLMを使用してツールを選択
            prompt = f"""
以下のタスクに必要なツールを選択してください。JSON形式で出力してください。

タスク: {state["input_message"]}
タスク分析: {state["task_analysis_result"]}

利用可能なツール:
- web_search: Web検索
- filesystem: ファイルシステム操作
- github: GitHub操作
- vscode: VSCode操作

出力形式:
{{
  "selected_tools": ["tool1", "tool2"]
}}
"""
            response = await self.client.post(
                f"{self.phi3_url}/generate",
                json={"prompt": prompt, "max_tokens": 256, "temperature": 0.3}
            )
            response.raise_for_status()
            data = response.json()
            llm_response = data.get("response", "")
            
            # JSONをパース
            json_match = re.search(r'\{[\s\S]*\}', llm_response)
            if json_match:
                tool_data = json.loads(json_match.group())
                state["selected_tools"] = tool_data.get("selected_tools", [])
            else:
                state["selected_tools"] = []
        except Exception as e:
            logger.warning(f"ツール選択失敗: {e}")
            state["selected_tools"] = []
        return state
    
    async def _llm_inference(self, state: AgentState) -> AgentState:
        """LLM推論を実行"""
        state["processing_steps"].append("llm_inference")
        
        # Qwenにリクエストを送信
        try:
            response = await self.client.post(
                f"{self.qwen_url}/generate",
                json={
                    "prompt": state["input_message"],
                    "max_tokens": 512,
                    "temperature": 0.7
                }
            )
            response.raise_for_status()
            data = response.json()
            state["llm_response"] = data.get("response", "")
        except Exception as e:
            logger.error(f"LLM推論失敗: {e}")
            state["llm_response"] = "推論に失敗しました"
        
        return state
    
    async def _memory_save(self, state: AgentState) -> AgentState:
        """記憶を保存（実際のサービス連携）"""
        state["processing_steps"].append("memory_save")
        try:
            # Mem0 APIを呼び出して記憶を保存
            mem0_url = os.getenv("MEM0_URL", "http://mem0:8080")
            memory = {
                "content": state["input_message"],
                "user_id": state["user_id"],
                "importance": 0.5,
                "category": "conversation",
                "timestamp": state.get("timestamp", "")
            }
            response = await self.client.post(
                f"{mem0_url}/memories",
                json=memory
            )
            response.raise_for_status()
            logger.info("記憶保存成功")
        except Exception as e:
            logger.warning(f"記憶保存失敗: {e}")
        return state
    
    async def _final_response(self, state: AgentState) -> AgentState:
        """最終応答を生成"""
        state["processing_steps"].append("final_response")
        state["final_response"] = state["llm_response"]
        return state
    
    async def process(self, state: AgentState) -> Dict[str, Any]:
        """グラフを実行"""
        result = await self.graph.ainvoke(state)
        return result

# プロセッサインスタンス
processor = LangGraphProcessor()

class AIState(BaseModel):
    user_id: str
    input_message: str
    emotion: Dict[str, Any] = {}
    short_term_context: Dict[str, Any] = {}
    long_term_context: List[str] = []
    important_memories: List[Dict[str, Any]] = []
    task_analysis: Dict[str, Any] = {}
    selected_tools: List[str] = []
    llm_response: str = ""
    final_response: str = ""
    processing_steps: List[str] = []

@app.post("/process")
async def process_message(state: AIState) -> Dict[str, Any]:
    """メッセージをLangGraphで処理"""
    # 状態を辞書に変換
    state_dict = state.dict()
    state_dict["processing_steps"] = []
    
    # グラフを実行
    result = await processor.process(state_dict)
    
    return result

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "langgraph"}
