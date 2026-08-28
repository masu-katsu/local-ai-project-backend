# Local AI Project

Docker Composeで動作するローカルAIチャットシステムです。
FastAPIがクライアントからのリクエストを受け、ChromaDBから関連する会話を検索し、Qwenで応答を生成します。
生成した会話はChromaDBとJSONLファイルへ保存されます。

## 構成

```text
クライアント（Unity / スマートフォン / HTTPクライアント）
        |
        v
FastAPI :8000
  |             |
  v             v
ChromaDB :8000  Qwen :8002
                  |
                  v
        Qwen2.5-Coder-3B GGUF
```

- `fastapi`: API、認証、履歴検索、Qwenへの転送
- `qwen`: `llama-cpp-python` によるGGUFモデル推論
- `chromadb`: 会話履歴のベクトル保存と類似検索
- `02_logs/conversations`: JSONL会話バックアップ
- `02_logs/system`: FastAPIシステムログ
- `03_models/qwen`: Qwen GGUFモデル

## 必要条件

- Windows
- Docker Desktop（Docker Compose対応）
- Qwen GGUFモデルファイル
- モデルファイルを次の場所へ配置

```text
03_models/qwen/Qwen2.5-Coder-3B-4bit.gguf
```

## 設定

`01_main/.env` を作成し、少なくともAPIキーを設定します。`.env` はGit管理対象外です。

```dotenv
FASTAPI_PORT=8000
API_KEY=ここに十分に長いランダムな秘密値を設定
QWEN_MAX_TOKENS=2048
QWEN_GPU_LAYERS=0
TIME_DECAY_HALF_LIFE_DAYS=30
APP_TIMEZONE=Asia/Tokyo
CORS_ORIGINS=http://localhost,http://127.0.0.1
```

`API_KEY` に初期値やサンプル値を使用しないでください。
APIキーを変更した場合、以後のリクエストには新しいキーを使用します。

`TIME_DECAY_HALF_LIFE_DAYS` は、古い会話の検索スコアをどの程度の期間で減衰させるかを日数で指定します。
`APP_TIMEZONE` は保存日付や「昨日」などの期間判定に使うタイムゾーンです。
`QWEN_GPU_LAYERS=0` はCPUモードです。GPU利用にはCUDA対応の `llama-cpp-python` ビルドとDocker DesktopのNVIDIA GPU設定が別途必要です。現行の標準イメージはCPU版です。

## 会話処理の流れ

1. FastAPIがリクエスト受付日時を `APP_TIMEZONE` 基準で取得します。
2. 質問に含まれる期間表現（昨日、先週、先月、去年、具体的な日付など）を解析します。
3. ChromaDBからユーザーIDと期間メタデータで事前に絞り込み、意味の近い候補を最大20件取得します。
4. 候補20件を距離と時間減衰で再評価し、上位3件だけをQwenへ渡します。
5. 現在日時、リクエスト受付日時、日付付きの過去会話、現在の質問を結合して回答を生成します。
6. 回答と受付日時をChromaDBおよびJSONLバックアップへ保存します。

期間指定がない場合も、ユーザーIDで分離した候補に対して時間減衰を適用します。

## 起動

PowerShellでプロジェクトのルートから実行します。

```powershell
Set-Location D:\local-ai-project\01_main
docker compose up -d --build
```

サービス状態を確認します。

```powershell
docker compose ps
```

初回起動時はQwenモデルの読み込みに時間がかかります。読み込み中はFastAPIのヘルス状態が `degraded` になり、完了すると `running` になります。GPU有効時はQwenのヘルス情報で `device: gpu` と表示されます。

## 停止・ログ

```powershell
Set-Location D:\local-ai-project\01_main
docker compose stop
docker compose logs -f fastapi qwen chromadb
```

コンテナを停止して削除する場合は次を使用します。ホスト側のログとモデルは削除されません。

```powershell
docker compose down
```

## API

FastAPIのベースURLは次のとおりです。

```text
http://localhost:8000
```

### ヘルスチェック

認証は不要です。

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
```

正常時の例:

```json
{
  "status": "running",
  "services": {
    "fastapi": "ok",
    "qwen": "ok"
  }
}
```

### チャット

`X-API-Key` ヘッダーが必要です。

```powershell
$headers = @{ "X-API-Key" = "設定したAPI_KEY" }
$body = @{ message = "こんにちは"; user_id = "default_user" } | ConvertTo-Json
Invoke-WebRequest -UseBasicParsing `
  -Uri http://localhost:8000/api/chat `
  -Method Post `
  -Headers $headers `
  -ContentType "application/json" `
  -Body $body
```

`/unity/predict` も `/api/chat` と同じ処理を実行します。

各チャットでは、サーバー側で取得した受付日時を検索基準時刻と生成プロンプトへ共通して使用します。

### 履歴取得

```powershell
Invoke-WebRequest -UseBasicParsing `
  -Uri "http://localhost:8000/api/history?user_id=default_user&limit=20" `
  -Headers $headers
```

`user_id` は英数字、`_`、`-`のみ使用でき、1から64文字までです。
`limit` は1から100まで指定できます。

### 履歴削除

ChromaDBの会話履歴とJSONLバックアップを削除します。削除後の復元はできません。

```powershell
Invoke-WebRequest -UseBasicParsing `
  -Uri http://localhost:8000/api/history `
  -Method Delete `
  -Headers $headers
```

## データ保存

| データ | 保存場所 |
| --- | --- |
| ChromaDB | `02_logs/chroma_db` |
| 会話JSONL | `02_logs/conversations` |
| FastAPIログ | `02_logs/system/fastapi.log` |
| Qwenモデル | `03_models/qwen` |

ChromaDBの会話メタデータには、`user_id`、`timestamp`、`timestamp_unix`、`request_datetime`、`request_timestamp_unix`、`date`、モデル名、質問、回答を保存します。
検索対象の文書本体にも受付日時と出来事の日付を含めるため、ベクトル検索後のプロンプトでも過去会話の時系列を参照できます。

ChromaDBの埋め込みモデルが初回検索時に取得されるため、初回チャットでは外部ネットワーク接続と追加の待ち時間が発生する場合があります。

## ネットワーク

FastAPIだけがホストへポート公開されます。QwenとChromaDBはCompose内部のバックエンドネットワークからのみアクセスできます。

- FastAPI: ホストの `8000` からアクセス
- Qwen: Compose内部の `qwen:8002`
- ChromaDB: Compose内部の `chromadb:8000`

## トラブルシュート

### Qwenが `offline` または `model_not_loaded`

1. モデルファイルの名前と配置を確認します。
2. `docker compose logs qwen` で読み込みエラーを確認します。
3. モデル読み込みが完了するまで待ちます。
4. `gpu_offload_supported: false` の場合、現在のイメージはCPU版です。GPU版へ変更する際はCUDA対応ビルドを用意してから検証してください。

### 履歴機能が使えない

1. `docker compose ps` でChromaDBが起動中か確認します。
2. `docker compose logs chromadb fastapi` で接続エラーを確認します。
3. `02_logs/chroma_db` が書き込み可能か確認します。

新しい日時メタデータを持たない既存レコードは、期間指定検索の対象になりません。必要に応じて履歴を削除して新しい形式で保存し直してください。

### `401 Unauthorized`

`X-API-Key` ヘッダーが設定した `API_KEY` と一致しているか確認します。
APIキーそのものをログやソースコードへ記録しないでください。

## 開発時の確認

```powershell
Set-Location D:\local-ai-project
python -m compileall -q 01_main
Set-Location 01_main
docker compose config --quiet
```

起動後の確認:

```powershell
Invoke-WebRequest -UseBasicParsing http://localhost:8000/health
docker compose ps
docker compose logs --tail=100 fastapi qwen chromadb
```

`/health` の `status` が `running`、`services.qwen` が `ok` になれば、モデル読み込みを含む基本的な起動確認は完了です。
