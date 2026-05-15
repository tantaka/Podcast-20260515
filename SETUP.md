# セットアップ手順

## 必要なもの

- GitHubアカウント
- Googleアカウント
- Gemini API キー（無料・クレカ不要）

---

## Step 1: Gemini API キーを取得する

1. https://aistudio.google.com/apikey を開く
2. 「APIキーを作成」をクリック
3. 表示されたキーをメモする

---

## Step 2: Google OAuth2.0 認証情報を取得する

Google Drive アップロードに使う OAuth2.0 のクレデンシャルを取得します。

### 2-1. OAuth クライアントIDを作成する

1. https://console.cloud.google.com/ を開く（Googleアカウントでログイン）
2. 左上のプロジェクトセレクタ → 「新しいプロジェクト」→ 任意の名前で作成
3. 左メニュー「APIとサービス」→「有効なAPIとサービス」→「APIを有効化」
4. 「Google Drive API」を検索して有効化
5. 左メニュー「認証情報」→「認証情報を作成」→「OAuthクライアントID」
6. アプリケーションの種類: **「ウェブアプリケーション」** を選択
7. 名前: 任意（例: "podcast-generator"）
8. 「承認済みのリダイレクト URI」→「URI を追加」→ 以下を入力:
   ```
   https://developers.google.com/oauthplayground
   ```
9. 「作成」をクリック
10. **クライアントID** と **クライアントシークレット** をメモする

### 2-2. OAuth2.0 Playground でリフレッシュトークンを取得する

1. https://developers.google.com/oauthplayground/ を開く
2. 右上の歯車アイコン → 「Use your own OAuth credentials」にチェック
3. Client ID と Client Secret に Step 2-1 の値を入力
4. 左側のスコープ一覧から「Drive API v3」→ `https://www.googleapis.com/auth/drive.file` を選択
5. 「Authorize APIs」をクリック → Googleアカウントでログイン → アクセスを許可
6. 「Exchange authorization code for tokens」をクリック
7. 表示された **Refresh token** をメモする

---

## Step 3: GitHubリポジトリを作成してシークレットを設定する

1. https://github.com/new でプライベートリポジトリを作成
2. このフォルダの内容をプッシュする:

```bash
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<ユーザー名>/<リポジトリ名>.git
git push -u origin main
```

3. GitHubリポジトリの「Settings」→「Secrets and variables」→「Actions」→「New repository secret」で以下を登録:

| シークレット名 | 値 |
|---|---|
| `GEMINI_API_KEY` | Step 1 のGemini APIキー |
| `GOOGLE_CLIENT_ID` | Step 2-1 のクライアントID |
| `GOOGLE_CLIENT_SECRET` | Step 2-1 のクライアントシークレット |
| `GOOGLE_REFRESH_TOKEN` | Step 2-2 のリフレッシュトークン |

---

## Step 4: 動作確認（手動実行）

1. GitHubリポジトリの「Actions」タブを開く
2. 「Daily Podcast Generation」ワークフローを選択
3. 「Run workflow」→ `target_date` に確認したい日付（例: `2026-05-14`）を入力して実行
4. ログを確認し、Google Driveの `/Podcast/` フォルダにファイルが生成されていれば成功

---

## Step 5: 自動実行の確認

毎日 **日本時間AM9:00** に自動実行されます（UTC 00:00 スケジュール）。

前日にClaude Codeの新バージョンがリリースされていればPodcastが生成され、
Google Driveの `/Podcast/{日付}/podcast.mp3` に保存されます。

---

## トラブルシューティング

### TTS APIが応答しない
- チャンクのwaitを増やす: `tts.py` の `CHUNK_WAIT_SEC` を大きくする（デフォルト: 8秒）

### リフレッシュトークンが期限切れになった
- Step 2-2 を再実行して新しいリフレッシュトークンを取得し、GitHubシークレットを更新する

### 対象リリースが見つからない
- Claude Codeが前日にリリースされていない場合は正常終了します（スキップ）
- `TARGET_DATE` を指定して手動実行することでテストできます
