"""Google Drive アップロードモジュール

OAuth 2.0 のリフレッシュトークンを使って認証し、
/Podcast/{date}/ フォルダに成果物をアップロードする。
"""

import json
import os
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from utils import logger

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
DRIVE_ROOT_FOLDER_NAME = "Podcast"


def _get_credentials() -> Credentials:
    """環境変数からOAuth2クレデンシャルを取得する。"""
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GOOGLE_REFRESH_TOKEN"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=os.environ["GOOGLE_CLIENT_ID"],
        client_secret=os.environ["GOOGLE_CLIENT_SECRET"],
        scopes=SCOPES,
    )
    creds.refresh(Request())
    return creds


def _get_or_create_folder(service, name: str, parent_id: str | None = None) -> str:
    """指定名のフォルダを検索し、なければ作成してIDを返す。"""
    query = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        query += f" and '{parent_id}' in parents"

    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        folder_id = files[0]["id"]
        logger.info(f"既存フォルダを使用: {name} (id={folder_id})")
        return folder_id

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = service.files().create(body=metadata, fields="id").execute()
    folder_id = folder["id"]
    logger.info(f"フォルダを作成しました: {name} (id={folder_id})")
    return folder_id


def upload_file(service, file_path: Path, folder_id: str, mime_type: str) -> dict:
    """ファイルをGoogle Driveの指定フォルダにアップロードする。"""
    metadata = {"name": file_path.name, "parents": [folder_id]}
    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)
    file = service.files().create(
        body=metadata, media_body=media, fields="id, webViewLink"
    ).execute()
    logger.info(f"アップロード完了: {file_path.name} → {file.get('webViewLink')}")
    return file


def upload_podcast(date: str, version: str, files: dict[str, Path]) -> dict:
    """Podcast成果物をGoogle Driveにアップロードする。

    files: {"research": Path, "script": Path, "audio_dir": Path, "mp3": Path}
    戻り値: {ファイル名: webViewLink}
    """
    logger.info(f"=== Google Drive アップロード開始: {version} ===")

    creds = _get_credentials()
    service = build("drive", "v3", credentials=creds)

    root_id = _get_or_create_folder(service, DRIVE_ROOT_FOLDER_NAME)
    date_id = _get_or_create_folder(service, date, parent_id=root_id)

    uploaded = {}

    if "mp3" in files and files["mp3"].exists():
        f = upload_file(service, files["mp3"], date_id, "audio/mpeg")
        uploaded["podcast.mp3"] = f.get("webViewLink", "")

    if "research" in files and files["research"].exists():
        f = upload_file(service, files["research"], date_id, "application/json")
        uploaded["research.json"] = f.get("webViewLink", "")

    if "script" in files and files["script"].exists():
        f = upload_file(service, files["script"], date_id, "application/json")
        uploaded["script.json"] = f.get("webViewLink", "")

    if "audio_dir" in files and files["audio_dir"].is_dir():
        wav_folder_id = _get_or_create_folder(service, "audio", parent_id=date_id)
        for wav in sorted(files["audio_dir"].glob("chunk_*.wav")):
            f = upload_file(service, wav, wav_folder_id, "audio/wav")
            uploaded[wav.name] = f.get("webViewLink", "")

    logger.info(f"アップロード完了: {len(uploaded)} ファイル")
    return uploaded


if __name__ == "__main__":
    import sys
    from pathlib import Path

    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if not date_arg:
        from utils import jst_yesterday_str
        date_arg = jst_yesterday_str()

    base = Path(__file__).parent.parent / "output"
    files = {
        "mp3": base / "audio" / date_arg / "podcast.mp3",
        "research": base / "research" / f"{date_arg}.json",
        "script": base / "scripts" / f"{date_arg}.json",
        "audio_dir": base / "audio" / date_arg,
    }

    result = upload_podcast(date_arg, date_arg, files)
    print(json.dumps(result, ensure_ascii=False, indent=2))
