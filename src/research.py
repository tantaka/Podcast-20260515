"""Claude Codeのリリース情報調査モジュール

情報源:
  1. GitHub Releases API (認証不要) でリリース一覧を取得
  2. Gemini 3.1 Flash-Lite + Google Search で X/ウェブの反応を収集
"""

import json
import os
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

from google import genai
from google.genai import types

from utils import logger, jst_yesterday_str, retry_fallback_models

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "research"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

GITHUB_API = "https://api.github.com/repos/anthropics/claude-code/releases"

PRIMARY_MODEL = "gemini-3.1-flash-lite-preview"
FALLBACK_MODEL = "gemini-2.5-flash-lite"


def _make_client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def fetch_claude_code_releases() -> list[dict]:
    """GitHub APIからClaude Codeのリリース一覧を取得する。"""
    logger.info("GitHub APIからClaude Codeリリース一覧を取得中...")
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    gh_token = os.environ.get("GITHUB_TOKEN")
    if gh_token:
        headers["Authorization"] = f"Bearer {gh_token}"

    resp = requests.get(GITHUB_API, headers=headers, timeout=30)
    resp.raise_for_status()
    releases = resp.json()
    logger.info(f"リリース {len(releases)} 件を取得しました")
    return releases


def find_target_release(releases: list[dict], target_date: str) -> dict | None:
    """指定日付（JST）に公開されたリリースを探す。"""
    for rel in releases:
        published = rel.get("published_at", "")
        if not published:
            continue
        pub_dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        pub_jst = pub_dt.astimezone(timezone(timedelta(hours=9)))
        if pub_jst.strftime("%Y-%m-%d") == target_date:
            logger.info(f"対象リリースを発見: {rel['tag_name']} ({published})")
            return rel
    return None


def _search_with_model(model_name: str, version: str, release_body: str) -> str:
    """指定モデルでGoogle Searchグラウンディングを使って情報収集する。"""
    logger.info(f"Gemini ({model_name}) でウェブ調査開始: Claude Code {version}")
    client = _make_client()

    grounding_tool = types.Tool(google_search=types.GoogleSearch())

    prompt = f"""Claude Code {version} のリリース情報について、以下の公式変更ログを元に、
X（旧Twitter）やウェブ上の開発者コミュニティの反応・評価・活用事例を含めて詳しく調査してください。

【公式変更ログ】
{release_body[:3000]}

以下の観点で詳細に情報を収集・整理してください：
1. 主な新機能・変更点の概要
2. X（旧Twitter）での開発者の反応や注目ポイント
3. 実際の活用方法・ユースケース
4. 既知の問題点・注意事項
5. 前バージョンからの改善点

日本語で詳しく整理してください。"""

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(tools=[grounding_tool]),
    )
    return response.text


def _search_primary(version: str, release_body: str) -> str:
    return _search_with_model(PRIMARY_MODEL, version, release_body)


def _search_fallback(version: str, release_body: str) -> str:
    return _search_with_model(FALLBACK_MODEL, version, release_body)


def research_release(version: str, release_body: str) -> str:
    """リリース情報をGemini Search Groundingで深掘り調査する。"""
    return retry_fallback_models(_search_primary, _search_fallback, version, release_body)


def run_research(target_date: str | None = None) -> dict | None:
    """調査のメイン処理。結果をJSONファイルに保存して返す。"""
    if target_date is None:
        target_date = jst_yesterday_str()

    logger.info(f"=== 調査開始: 対象日付 = {target_date} ===")

    releases = fetch_claude_code_releases()
    release = find_target_release(releases, target_date)

    if release is None:
        logger.warning(f"{target_date} に公開されたClaude Codeリリースが見つかりませんでした")
        return None

    version = release["tag_name"]
    body = release.get("body", "変更ログなし")
    html_url = release.get("html_url", "")

    research_text = research_release(version, body)

    result = {
        "target_date": target_date,
        "version": version,
        "release_url": html_url,
        "release_body": body,
        "research_text": research_text,
    }

    out_path = OUTPUT_DIR / f"{target_date}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"調査結果を保存しました: {out_path}")

    return result


if __name__ == "__main__":
    import sys
    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    result = run_research(date_arg)
    if result:
        print(f"調査完了: {result['version']}")
    else:
        print("対象リリースが見つかりませんでした")
        sys.exit(1)
