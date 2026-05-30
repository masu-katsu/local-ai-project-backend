from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import logging

app = FastAPI(title="LangGraph Service")
logger = logging.getLogger(__name__)

class AIState(BaseModel):
    user_id: str
    input_message: str
    emotion: Dict[str, Any]
    short_term_context: Dict[str, Any]
    long_term_context: List[str]
    important_memories: List[Dict[str, Any]]
    task_analysis: Dict[str, Any]
    selected_tools: List[str]
    llm_response: str
    final_response: str
    processing_steps: List[str]

@app.post("/process")
async def process_message(state: AIState) -> Dict[str, Any]:
    """メッセージをLangGraphで処理"""
    # 簡易実装（実際はLangGraphを使用）
    processing_steps = []
    
    # Step 1: 感情更新
    processing_steps.append("emotion_update")
    
    # Step 2: 記憶検索
    processing_steps.append("memory_search")
    
    # Step 3: タスク分析
    processing_steps.append("task_analysis")
    
    # Step 4: ツール選択
    processing_steps.append("tool_selection")
    
    # Step 5: LLM推論
    processing_steps.append("llm_inference")
    
    # Step 6: 記憶保存
    processing_steps.append("memory_save")
    
    # Step 7: 最終応答生成
    processing_steps.append("final_response")
    
    state.processing_steps = processing_steps
    state.final_response = state.input_message  # 簡易実装
    
    return state.dict()

@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "langgraph"}
