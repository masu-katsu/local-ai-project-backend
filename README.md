# ローカルAIアプリ（Local AI Stack）

Dockerコンテナ群でローカルAI（Qwen）を動かし、**FastAPIを司令塔（ゲートウェイ）として外部（Unity・スマホなど）とAIモデル間の通信を仲介する**ためのプロジェクトです。すべてローカル環境で完結し、クラウドAPIへの依存なしに動作します。

## 構成図

```
Unity / スマホ / 外部クライアント
        │  HTTP (X-API-Key ヘッダ必須)
        ▼
┌─────────────────────┐
│  FastAPI（司令塔）    │  :8000  ← frontend / backend 両方に参加
│  - APIキー認証        │
│  - Qwen直接送信       │
│  - 会話履歴の保存/検索 │
└──────────┬──────────┘
           │ backend（internalネットワーク・外部非公開）
   ┌───────┼────────┬─────────────┐
   ▼                ▼             ▼
┌────────┐     ┌────────┐   ┌───────────┐
│  Qwen   │     │ ChromaDB │
│ 実行AI  │     │ ベクトルDB │
│ :8002   │     │  :8000    │
│ CPU/GPU │     │ 履歴検索用 │
└────────┘     └───────────┘
```

## コンポーネント

### 1. FastAPI（`01_main/fastapi`）— 司令塔
すべてのリクエストを受け付けるゲートウェイ。
- `X-API-Key` ヘッダによるAPIキー認証ミドルウェア（`/health` `/docs` などは除外）
- リクエストごとに ChromaDB から関連する過去会話を検索
- 受け取った入力をそのままQwenへ送信し、応答を生成させる（`router.py`）
- 会話をChromaDB＋JSONLファイル（`02_logs/conversations/`）の両方に保存（`history.py`）

**主なエンドポイント**
| メソッド | パス | 内容 |
|---|---|---|
| GET | `/health`, `/api/health` | 各サービスの死活確認（認証不要） |
| POST | `/api/chat`, `/unity/predict` | チャット本体（同じ処理を2つのパスで公開） |
| GET | `/api/history` | 会話履歴取得（`user_id`, `limit`） |
| DELETE | `/api/history` | ChromaDB上の会話履歴を全削除 |

### 2. Qwen（`01_main/qwen`）— 実行AI（コード生成・長文生成）
- FastAPI から直接受け取った入力をもとに応答を生成する
- CPU/GPUを環境変数で切り替え可能（`N_GPU_LAYERS=0` でCPU動作）

### 3. ChromaDB — 会話履歴のベクトルストア
- ユーザー発話とAI応答のペアを埋め込み、意味的な類似度で過去の関連会話を検索
- `max_distance` で関連性の低い結果を除外

## ディレクトリ構成

```
local-ai-project/
├── 01_main/
│   ├── docker-compose.yml
│   ├── .env                    # 環境変数（Git管理外にすること）
│   ├── fastapi/
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── app/
│   │       ├── main.py         # エンドポイント定義・認証
│   │       ├── router.py       # 意図分類・AI振り分け
│   │       └── history.py      # ChromaDB連携・履歴保存
│   └── qwen/
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/main.py
├── 02_logs/                     # 会話ログ・ChromaDB永続化データ
│   ├── conversations/*.jsonl
│   ├── chroma_db/
│   └── system/
├── 03_models/                   # GGUFモデル格納先（各自配置）
│   └── qwen/
└── config.json
```

## セットアップ

### 1. モデルファイルの配置
以下にGGUF形式のモデルファイルを配置してください（`docker-compose.yml` の volumes でコンテナにマウントされます）。

```
03_models/qwen/Qwen2.5-Coder-3B-4bit.gguf
```

### 2. 環境変数の設定
`01_main/.env` を編集します。

```env
FASTAPI_PORT=8000
API_KEY=<必ず自分で生成した値に変更してください>

QWEN_MAX_TOKENS=2048

BING_API_KEY=          # Web検索を使う場合のみ設定
```

> ⚠️ **重要**: サンプルの `.env` には既に具体的なAPIキーの値が入った状態でリポジトリに含まれています。外部公開・共有前に必ず新しい値へ変更し、`.env` を `.gitignore` に含めてコミット対象から外してください。

### 3. 起動

```bash
cd 01_main
docker compose up -d --build
```

起動確認:
```bash
curl http://localhost:8000/health
```

### 4. チャットの呼び出し例

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "X-API-Key: <.envで設定したAPI_KEY>" \
  -d '{"message": "こんにちは", "user_id": "default_user"}'
```

`force_model` は現在の実装では未使用です。入力はそのまま Qwen に送信されます。

## ネットワーク設計

- `frontend` ネットワーク: FastAPIのみ参加。外部（Unity/スマホ）からアクセス可能な唯一の経路。
- `backend` ネットワーク（`internal: true`）: FastAPI・Qwen・ChromaDBのみが参加し、外部から直接アクセス不可。Qwenは `backend` にしか属さないため、コンテナ外から直接叩くことはできません。

## リソース制限
- Qwenは `N_GPU_LAYERS` で GPU 使用量を調整でき、`0` の場合はGPUなし環境でもCPUのみで起動します。

## ログ・データの永続化

| 種類 | 保存先 |
|---|---|
| 会話ログ（バックアップ用JSONL） | `02_logs/conversations/{user_id}_{日付}.jsonl` |
| ChromaDBデータ | `02_logs/chroma_db/` |
| システムログ（FastAPI） | コンテナ内 `/app/logs/system/fastapi.log` |

## 既知の注意点

- CORSは現状 `allow_origins=["*"]` で全許可の開発設定になっているため、本番運用時はオリジンを制限してください。
- `.gitignore` にマージコンフリクトの解消漏れ（`<<<<<<<` 等のマーカー）が残っています。整理してからコミットすることを推奨します。
- `fastapi/app/__pycache__` 内には `router.py` 等に対応しない古いモジュール（`memory_organizer` や `vision_processor` など）のキャッシュファイルが残存しています。過去に存在した機能の名残と思われるため、実体の `.py` がないことを確認の上で不要であれば削除してください。
