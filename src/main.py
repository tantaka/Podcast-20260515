"""Podcast自動生成メインエントリーポイント

実行フロー:
  1. GitHub API でClaude Code前日リリース確認
  2. Gemini Search Grounding で調査 → research.json
  3. Gemini Flash-Lite で台本生成 → script.json
  4. Gemini TTS で音声生成 → chunk_*.wav
  5. pydub + FFmpeg でMP3変換 → podcast.mp3
  6. Google Drive にアップロード
  7. 履歴更新
"""

import json
import os
import sys
from pathlib import Path

from utils import logger, jst_yesterday_str
from history import is_already_generated, add_episode
from research import run_research
from script_gen import generate_script
from tts import generate_audio_chunks
from audio import process_audio
from drive_upload import upload_podcast


def main():
    target_date = os.environ.get("TARGET_DATE") or jst_yesterday_str()
    logger.info("=" * 60)
    logger.info(f"Podcast自動生成開始: 対象日付 = {target_date}")
    logger.info("=" * 60)

    # --- Step 1: 調査 ---
    research_path = (
        Path(__file__).parent.parent / "output" / "research" / f"{target_date}.json"
    )
    if research_path.exists():
        logger.info(f"調査結果が既に存在します。スキップ: {research_path}")
        with open(research_path, encoding="utf-8") as f:
            research = json.load(f)
    else:
        research = run_research(target_date)
        if research is None:
            logger.warning("対象リリースが見つかりませんでした。処理を終了します。")
            sys.exit(0)

    version = research["version"]
    logger.info(f"対象バージョン: {version}")

    # --- 重複チェック ---
    if is_already_generated(version):
        logger.info(f"{version} は生成済みです。処理を終了します。")
        sys.exit(0)

    # --- Step 2: 台本生成 ---
    script_path = (
        Path(__file__).parent.parent / "output" / "scripts" / f"{target_date}.json"
    )
    if script_path.exists():
        logger.info(f"台本が既に存在します。スキップ: {script_path}")
        with open(script_path, encoding="utf-8") as f:
            script = json.load(f)
    else:
        script = generate_script(research)

    # --- Step 3: 音声生成 ---
    wav_paths = generate_audio_chunks(script)

    # --- Step 4: MP3変換 ---
    mp3_path = process_audio(wav_paths, target_date, version)

    # --- Step 5: Google Drive アップロード ---
    base = Path(__file__).parent.parent / "output"
    files = {
        "mp3": mp3_path,
        "research": research_path,
        "script": script_path,
        "audio_dir": base / "audio" / target_date,
    }
    uploaded = upload_podcast(target_date, version, files)
    mp3_url = uploaded.get("podcast.mp3", "")

    # --- Step 6: 履歴更新 ---
    title = f"Claude Code {version} 変更点解説"
    add_episode(version, target_date, mp3_url, title)

    logger.info("=" * 60)
    logger.info("Podcast生成完了!")
    logger.info(f"  バージョン: {version}")
    logger.info(f"  Drive URL:  {mp3_url}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()
