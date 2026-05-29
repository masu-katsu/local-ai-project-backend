# Phase4 詳細設計: マルチモーダル対応

## 概要

Phase4では、Web Search（SearxNG）、Whisper（音声認識）、Piper（音声合成）を実装する。

**目的**:
- プライベートWeb検索（SearxNG）
- 音声入力対応（Whisper）
- 音声出力対応（Piper）

---

## コンポーネント詳細

### 1. SearxNG（プライベートWeb検索）

#### 役割
- 最新情報取得
- エラー解決
- GitHub検索
- ドキュメント検索
- プライバシー保護

#### Docker設定

```yaml
# docker-compose.ymlに追加

searxng:
  image: searxng/searxng:latest
  container_name: ai-searxng
  ports:
    - "8082:8080"
  volumes:
    - ./searxng/settings.yml:/etc/searxng/settings.yml:ro
  environment:
    - SEARXNG_BASE_URL=http://localhost:8082
  networks:
    - backend
  restart: unless-stopped
```

#### SearxNG設定

```yaml
# searxng/settings.yml

general:
  debug: false
  instance_name: "Local AI Search"
  contact_url: false

search:
  safe_search: 0
  autocomplete: ""
  max_page: 3

server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "your-secret-key-here"
  method: "GET"
  base_url: false

engines:
  - name: google
    engine: google
    shortcut: go
    disabled: false
  
  - name: bing
    engine: bing
    shortcut: bi
    disabled: false
  
  - name: duckduckgo
    engine: duckduckgo
    shortcut: dd
    disabled: false
  
  - name: github
    engine: github
    shortcut: gh
    disabled: false
```

#### SearxNGクライアント実装

```python
# app/searxng_client.py

import logging
import httpx
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class SearxNGClient:
    """SearxNGクライアント"""
    
    def __init__(self, base_url: str = "http://searxng:8080"):
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        logger.info(f"SearxNGClient初期化: {base_url}")
    
    async def search(
        self,
        query: str,
        engines: Optional[List[str]] = None,
        max_results: int = 10,
        category: str = "general"
    ) -> List[Dict[str, Any]]:
        """
        検索を実行
        
        Args:
            query: 検索クエリ
            engines: 使用するエンジン（Noneなら全て）
            max_results: 最大結果数
            category: カテゴリ（general, images, videos, etc.）
        
        Returns:
            検索結果のリスト
        """
        params = {
            "q": query,
            "format": "json",
            "engines": ",".join(engines) if engines else "",
            "categories": category
        }
        
        try:
            response = await self.client.get(
                f"{self.base_url}/search",
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            results = data.get("results", [])[:max_results]
            
            logger.info(f"SearxNG検索: {query} -> {len(results)}件")
            return results
            
        except Exception as e:
            logger.error(f"SearxNG検索エラー: {e}")
            return []
    
    async def search_github(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """GitHub検索"""
        return await self.search(
            query=query,
            engines=["github"],
            max_results=max_results
        )
    
    async def search_images(
        self,
        query: str,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """画像検索"""
        return await self.search(
            query=query,
            category="images",
            max_results=max_results
        )
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
```

---

### 2. Whisper（音声認識）

#### 役割
- 音声入力対応
- 音声→テキスト変換
- 多言語対応

#### Docker設定

```yaml
# docker-compose.ymlに追加

whisper:
  build: ./whisper
  container_name: ai-whisper
  ports:
    - "8083:8000"
  environment:
    - MODEL_PATH=/models/whisper
    - MODEL_NAME=base
  volumes:
    - ../03_models/whisper:/models/whisper:ro
  networks:
    - backend
  deploy:
    resources:
      limits:
        memory: 4G
      reservations:
        memory: 2G
  restart: unless-stopped
```

#### Whisper Dockerfile

```dockerfile
# whisper/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# システム依存
RUN apt-get update && apt-get install -y \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Whisper requirements.txt

```
fastapi==0.115.0
uvicorn==0.30.0
openai-whisper==20240930
torch==2.1.0
torchaudio==2.1.0
python-multipart
```

#### Whisperサービス実装

```python
# whisper/app/main.py

from fastapi import FastAPI, UploadFile, File
from pydantic import BaseModel
import whisper
import logging
import os

app = FastAPI(title="Whisper Service")
logger = logging.getLogger(__name__)

# モデルロード
MODEL_PATH = os.getenv("MODEL_PATH", "/models/whisper")
MODEL_NAME = os.getenv("MODEL_NAME", "base")

logger.info(f"Whisperモデルロード中: {MODEL_NAME}")
model = whisper.load_model(MODEL_NAME, download_root=MODEL_PATH)
logger.info("Whisperモデルロード完了")

class TranscriptionResponse(BaseModel):
    text: str
    language: str
    duration: float

@app.post("/transcribe")
async def transcribe(audio: UploadFile = File(...)) -> TranscriptionResponse:
    """
    音声をテキストに変換
    
    Args:
        audio: 音声ファイル
    
    Returns:
        変換結果
    """
    logger.info(f"音声認識リクエスト: {audio.filename}")
    
    # 一時ファイルに保存
    temp_path = f"/tmp/{audio.filename}"
    with open(temp_path, "wb") as f:
        f.write(await audio.read())
    
    try:
        # 音声認識
        result = model.transcribe(temp_path, language="ja")
        
        logger.info(f"音声認識完了: {len(result['text'])}文字")
        
        return TranscriptionResponse(
            text=result["text"],
            language=result["language"],
            duration=result.get("duration", 0.0)
        )
    except Exception as e:
        logger.error(f"音声認識エラー: {e}")
        raise
    finally:
        # 一時ファイル削除
        if os.path.exists(temp_path):
            os.remove(temp_path)

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "ok", "model": MODEL_NAME}
```

#### Whisperクライアント実装

```python
# app/voice_input.py

import logging
import httpx
from typing import Optional

logger = logging.getLogger(__name__)

class VoiceInputClient:
    """Whisperクライアント"""
    
    def __init__(self, whisper_url: str = "http://whisper:8000"):
        self.whisper_url = whisper_url
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"VoiceInputClient初期化: {whisper_url}")
    
    async def transcribe(
        self,
        audio_data: bytes,
        filename: str = "audio.wav"
    ) -> Optional[str]:
        """
        音声をテキストに変換
        
        Args:
            audio_data: 音声データ（bytes）
            filename: ファイル名
        
        Returns:
            変換されたテキスト
        """
        files = {
            "audio": (filename, audio_data, "audio/wav")
        }
        
        try:
            response = await self.client.post(
                f"{self.whisper_url}/transcribe",
                files=files
            )
            response.raise_for_status()
            
            data = response.json()
            text = data.get("text", "")
            
            logger.info(f"音声認識完了: {len(text)}文字")
            return text
            
        except Exception as e:
            logger.error(f"音声認識エラー: {e}")
            return None
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
```

---

### 3. Piper（音声合成）

#### 役割
- AI音声出力
- テキスト→音声変換
- 多言語対応

#### Docker設定

```yaml
# docker-compose.ymlに追加

piper:
  build: ./piper
  container_name: ai-piper
  ports:
    - "8084:8000"
  environment:
    - MODEL_PATH=/models/piper
    - VOICE_NAME=ja_jp_pt_multispeaker
  volumes:
    - ../03_models/piper:/models/piper:ro
  networks:
    - backend
  deploy:
    resources:
      limits:
        memory: 2G
      reservations:
        memory: 1G
  restart: unless-stopped
```

#### Piper Dockerfile

```dockerfile
# piper/Dockerfile

FROM python:3.11-slim

WORKDIR /app

# システム依存
RUN apt-get update && apt-get install -y \
    espeak-ng \
    libespeak1 \
    libespeak-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

#### Piper requirements.txt

```
fastapi==0.115.0
uvicorn==0.30.0
piper-tts==1.2.0
torch==2.1.0
numpy
```

#### Piperサービス実装

```python
# piper/app/main.py

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from piper import PiperVoice
import logging
import os
import io

app = FastAPI(title="Piper Service")
logger = logging.getLogger(__name__)

# モデルロード
MODEL_PATH = os.getenv("MODEL_PATH", "/models/piper")
VOICE_NAME = os.getenv("VOICE_NAME", "ja_jp_pt_multispeaker")

logger.info(f"Piperモデルロード中: {VOICE_NAME}")
model_path = os.path.join(MODEL_PATH, VOICE_NAME, f"{VOICE_NAME}.onnx")
config_path = os.path.join(MODEL_PATH, VOICE_NAME, f"{VOICE_NAME}.onnx.json")

voice = PiperVoice.load(model_path, config_path)
logger.info("Piperモデルロード完了")

class SynthesizeRequest(BaseModel):
    text: str
    speed: float = 1.0

class SynthesizeResponse(BaseModel):
    audio_data: str  # base64エンコード
    duration: float

@app.post("/synthesize")
async def synthesize(request: SynthesizeRequest) -> SynthesizeResponse:
    """
    テキストを音声に変換
    
    Args:
        request: 合成リクエスト
    
    Returns:
        音声データ（base64エンコード）
    """
    logger.info(f"音声合成リクエスト: {len(request.text)}文字")
    
    try:
        # 音声合成
        audio_stream = io.BytesIO()
        
        for audio_chunk in voice.synthesize_stream(request.text, speed=request.speed):
            audio_stream.write(audio_chunk)
        
        audio_data = audio_stream.getvalue()
        
        # Base64エンコード
        import base64
        audio_base64 = base64.b64encode(audio_data).decode("utf-8")
        
        # 時間を推定（簡易）
        duration = len(request.text) * 0.1  # 文字数 × 0.1秒
        
        logger.info(f"音声合成完了: {len(audio_data)}bytes")
        
        return SynthesizeResponse(
            audio_data=audio_base64,
            duration=duration
        )
        
    except Exception as e:
        logger.error(f"音声合成エラー: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """ヘルスチェック"""
    return {"status": "ok", "voice": VOICE_NAME}
```

#### Piperクライアント実装

```python
# app/voice_output.py

import logging
import httpx
import base64
from typing import Optional

logger = logging.getLogger(__name__)

class VoiceOutputClient:
    """Piperクライアント"""
    
    def __init__(self, piper_url: str = "http://piper:8000"):
        self.piper_url = piper_url
        self.client = httpx.AsyncClient(timeout=60.0)
        logger.info(f"VoiceOutputClient初期化: {piper_url}")
    
    async def synthesize(
        self,
        text: str,
        speed: float = 1.0
    ) -> Optional[bytes]:
        """
        テキストを音声に変換
        
        Args:
            text: テキスト
            speed: 再生速度
        
        Returns:
            音声データ（bytes）
        """
        payload = {
            "text": text,
            "speed": speed
        }
        
        try:
            response = await self.client.post(
                f"{self.piper_url}/synthesize",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            audio_base64 = data.get("audio_data", "")
            
            # Base64デコード
            audio_data = base64.b64decode(audio_base64)
            
            logger.info(f"音声合成完了: {len(audio_data)}bytes")
            return audio_data
            
        except Exception as e:
            logger.error(f"音声合成エラー: {e}")
            return None
    
    async def close(self):
        """クライアントをクローズ"""
        await self.client.aclose()
```

---

## FastAPIへの統合

### main.pyの更新

```python
# app/main.pyに追加

from app.searxng_client import SearxNGClient
from app.voice_input_client import VoiceInputClient
from app.voice_output_client import VoiceOutputClient

# 環境変数追加
SEARXNG_URL = os.getenv("SEARXNG_URL", "http://searxng:8080")
WHISPER_URL = os.getenv("WHISPER_URL", "http://whisper:8000")
PIPER_URL = os.getenv("PIPER_URL", "http://piper:8000")

# 初期化
searxng_client = SearxNGClient(searxng_url=SEARXNG_URL)
voice_input_client = VoiceInputClient(whisper_url=WHISPER_URL)
voice_output_client = VoiceOutputClient(piper_url=PIPER_URL)

# startupイベントで初期化確認
@app.on_event("startup")
async def startup_event():
    # 既存の初期化...
    
    # SearxNG確認
    logger.info(f"  SearxNG: {SEARXNG_URL}")
    
    # Whisper確認
    logger.info(f"  Whisper: {WHISPER_URL}")
    
    # Piper確認
    logger.info(f"  Piper: {PIPER_URL}")
```

### Web Search Toolの更新

```python
# app/tools/web_search_tool.pyを更新

from app.searxng_client import SearxNGClient

class WebSearchTool(BaseTool):
    """Web検索ツール"""
    
    def __init__(self, searxng_url: str = "http://searxng:8080"):
        super().__init__()
        self.searxng_client = SearxNGClient(searxng_url)
    
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
        engines = params.get("engines")
        
        try:
            results = await self.searxng_client.search(
                query=query,
                engines=engines,
                max_results=max_results
            )
            
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
```

### 新規APIエンドポイント

```python
# Web検索
@app.post("/api/search")
async def web_search(
    query: str,
    max_results: int = 5,
    engines: Optional[List[str]] = None
):
    """Web検索を実行"""
    results = await searxng_client.search(
        query=query,
        engines=engines,
        max_results=max_results
    )
    return {"query": query, "results": results, "count": len(results)}

@app.post("/api/search/github")
async def github_search(
    query: str,
    max_results: int = 10
):
    """GitHub検索を実行"""
    results = await searxng_client.search_github(query, max_results)
    return {"query": query, "results": results, "count": len(results)}

# 音声入力
@app.post("/api/voice/transcribe")
async def transcribe_audio(audio: UploadFile = File(...)):
    """音声をテキストに変換"""
    audio_data = await audio.read()
    text = await voice_input_client.transcribe(audio_data, audio.filename)
    
    if text is None:
        raise HTTPException(status_code=500, detail="音声認識に失敗しました")
    
    return {"text": text}

# 音声出力
@app.post("/api/voice/synthesize")
async def synthesize_speech(
    text: str,
    speed: float = 1.0
):
    """テキストを音声に変換"""
    audio_data = await voice_output_client.synthesize(text, speed)
    
    if audio_data is None:
        raise HTTPException(status_code=500, detail="音声合成に失敗しました")
    
    # Base64エンコードして返す
    import base64
    audio_base64 = base64.b64encode(audio_data).decode("utf-8")
    
    return {
        "audio_data": audio_base64,
        "format": "wav",
        "text": text
    }
```

---

## 音声フロー統合

### LangGraphノード追加

```python
# app/graph_nodes.pyに追加

async def voice_input_node(state: AIState) -> AIState:
    """音声入力を処理"""
    # 音声データが含まれている場合
    if "audio_data" in state:
        from app.voice_input_client import VoiceInputClient
        
        voice_client = VoiceInputClient()
        text = await voice_client.transcribe(
            state["audio_data"],
            state.get("audio_filename", "audio.wav")
        )
        
        if text:
            state["input_message"] = text
            state["processing_steps"].append("voice_transcription")
    
    return state

async def voice_output_node(state: AIState) -> AIState:
    """音声出力を生成"""
    from app.voice_output_client import VoiceOutputClient
    
    voice_client = VoiceOutputClient()
    
    # 感情に応じて速度を調整
    speed = 1.0
    if state.get("emotion"):
        energy = state["emotion"].get("energy", 50)
        speed = 0.8 + (energy / 250.0)
    
    audio_data = await voice_client.synthesize(
        state["final_response"],
        speed=speed
    )
    
    if audio_data:
        import base64
        state["audio_output"] = base64.b64encode(audio_data).decode("utf-8")
        state["processing_steps"].append("voice_synthesis")
    
    return state
```

---

## Unity連携

### 音声入力

```csharp
// Unity側の音声入力実装

public class VoiceInput : MonoBehaviour
{
    private AudioClip recordingClip;
    private int recordingLength = 10; // 秒
    
    public void StartRecording()
    {
        recordingClip = Microphone.Start(null, false, recordingLength, 44100);
    }
    
    public void StopRecording()
    {
        Microphone.End(null);
        
        // 音声データを取得
        float[] samples = new float[recordingClip.samples * recordingClip.channels];
        recordingClip.GetData(samples, 0);
        
        // WAVに変換して送信
        byte[] wavData = AudioToWav(samples, recordingClip);
        
        // APIに送信
        StartCoroutine(SendAudio(wavData));
    }
    
    IEnumerator SendAudio(byte[] audioData)
    {
        WWWForm form = new WWWForm();
        form.AddBinaryData("audio", audioData, "recording.wav");
        
        using (UnityWebRequest www = UnityWebRequest.Post("http://localhost:8000/api/voice/transcribe", form))
        {
            yield return www.SendWebRequest();
            
            if (www.result == UnityWebRequest.Result.Success)
            {
                string response = www.downloadHandler.text;
                // テキストをAIに送信
                aiManager.SendMessage(response);
            }
        }
    }
}
```

### 音声出力

```csharp
// Unity側の音声出力実装

public class VoiceOutput : MonoBehaviour
{
    private AudioSource audioSource;
    
    void Start()
    {
        audioSource = GetComponent<AudioSource>();
    }
    
    public void PlayAudio(string base64Audio)
    {
        byte[] audioData = System.Convert.FromBase64String(base64Audio);
        AudioClip clip = WavToAudioClip(audioData);
        
        audioSource.clip = clip;
        audioSource.Play();
    }
}
```

---

## テスト計画

### ユニットテスト

```python
# tests/test_searxng_client.py

import pytest
from app.searxng_client import SearxNGClient

@pytest.mark.asyncio
async def test_searxng_search():
    client = SearxNGClient()
    
    results = await client.search("Python", max_results=5)
    
    assert len(results) > 0
    assert "title" in results[0]

@pytest.mark.asyncio
async def test_searxng_github_search():
    client = SearxNGClient()
    
    results = await client.search_github("fastapi", max_results=5)
    
    assert len(results) > 0
```

### 統合テスト

```python
# tests/test_voice_integration.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_voice_transcription():
    # テスト用音声ファイルが必要
    pass

@pytest.mark.asyncio
async def test_voice_synthesis():
    async with AsyncClient(base_url="http://localhost:8000") as client:
        response = await client.post(
            "/api/voice/synthesize",
            json={"text": "こんにちは", "speed": 1.0},
            headers={"X-API-Key": "test-key"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "audio_data" in data
```

---

## デプロイ手順

### 1. SearxNGサービス構築

```bash
cd 01_main
mkdir -p searxng
# settings.ymlを作成
docker-compose up -d searxng
```

### 2. Whisperサービス構築

```bash
mkdir -p whisper/app
# Dockerfile, requirements.txt, main.pyを作成
# モデルをダウンロード: 03_models/whisper/
docker-compose build whisper
docker-compose up -d whisper
```

### 3. Piperサービス構築

```bash
mkdir -p piper/app
# Dockerfile, requirements.txt, main.pyを作成
# モデルをダウンロード: 03_models/piper/
docker-compose build piper
docker-compose up -d piper
```

### 4. FastAPI更新

```bash
cd fastapi
# requirements.txtに追加
# 新規モジュールを作成
# app/searxng_client.py
# app/voice_input_client.py
# app/voice_output_client.py

# main.pyを更新
# app/tools/web_search_tool.pyを更新
```

### 5. 環境変数設定

```bash
# .envに追加
SEARXNG_URL=http://searxng:8080
WHISPER_URL=http://whisper:8000
PIPER_URL=http://piper:8000
```

### 6. 再起動

```bash
docker-compose up -d fastapi
```

---

## 依存関係

```
Phase4コンポーネントの依存関係:

SearxNG
  └─ WebSearchTool (Phase3)

Whisper
  ├─ VoiceInputClient
  └─ LangGraph (voice_input_node)

Piper
  ├─ VoiceOutputClient
  └─ LangGraph (voice_output_node)

FastAPI main.py
  ├─ SearxNGClient
  ├─ VoiceInputClient
  └─ VoiceOutputClient
```

---

## 次のステップ

Phase4完了後、以下を確認:
- SearxNGが正しく検索できるか
- Whisperが音声を認識できるか
- Piperが音声を合成できるか
- Unityとの音声連携が機能しているか

確認後、Phase5（MCP, Vision, 自律Agent）へ進む。
