from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List, Optional, TypedDict, Annotated
import logging
import operator
import os
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
        """感情を更新"""
        state["processing_steps"].append("emotion_update")
        # 感情検出ロジック（簡易実装）
        if any(word in state["input_message"].lower() for word in ["嬉しい", "楽しい", "すごい"]):
            state["emotion"] = {"mood": "positive", "energy": 80}
        elif any(word in state["input_message"].lower() for word in ["悲しい", "辛い", "残念"]):
            state["emotion"] = {"mood": "negative", "energy": 30}
        else:
            state["emotion"] = {"mood": "neutral", "energy": 50}
        return state
    
    async def _memory_search(self, state: AgentState) -> AgentState:
        """記憶を検索"""
        state["processing_steps"].append("memory_search")
        # 記憶検索ロジック（簡易実装）
        state["long_term_context"] = ["過去の会話コンテキスト1", "過去の会話コンテキスト2"]
        return state
    
    async def _task_analysis(self, state: AgentState) -> AgentState:
        """タスクを分析"""
        state["processing_steps"].append("task_analysis")
        # タスク分析ロジック（簡易実装）
        state["task_analysis_result"] = {
            "is_task": False,
            "task_type": None,
            "priority": "medium"
        }
        return state
    
    async def _tool_selection(self, state: AgentState) -> AgentState:
        """ツールを選択"""
        state["processing_steps"].append("tool_selection")
        # ツール選択ロジック（簡易実装）
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
        """記憶を保存"""
        state["processing_steps"].append("memory_save")
        # 記憶保存ロジック（簡易実装）
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
