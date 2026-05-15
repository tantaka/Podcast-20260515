"""過去Podcastの履歴管理・重複チェック"""

import json
import os
from pathlib import Path
from utils import logger

HISTORY_FILE = Path(__file__).parent.parent / "history.json"


def load_history() -> dict:
    if not HISTORY_FILE.exists():
        return {"episodes": []}
    with open(HISTORY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_history(history: dict) -> None:
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    logger.info(f"履歴を保存しました: {HISTORY_FILE}")


def is_already_generated(version: str) -> bool:
    """指定バージョンのPodcastが過去に生成済みか確認する。"""
    history = load_history()
    versions = [ep.get("version") for ep in history.get("episodes", [])]
    if version in versions:
        logger.info(f"バージョン {version} は既に生成済みです。スキップします。")
        return True
    return False


def add_episode(version: str, date: str, drive_url: str, title: str) -> None:
    """生成済みエピソードを履歴に追加する。"""
    history = load_history()
    history["episodes"].append({
        "version": version,
        "date": date,
        "drive_url": drive_url,
        "title": title,
    })
    save_history(history)
    logger.info(f"履歴に追加しました: version={version}, date={date}")


def get_covered_versions() -> list[str]:
    history = load_history()
    return [ep.get("version") for ep in history.get("episodes", [])]
