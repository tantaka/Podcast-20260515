"""台本生成モジュール

Gemini Flash-Lite で男女二人の会話形式台本を生成し、
TTS用に2000文字未満のチャンクに分割する。
"""

import json
import os
import re
from pathlib import Path

from google import genai
from google.genai import types

from utils import logger, retry_fallback_models

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "scripts"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PRIMARY_MODEL = "gemini-3.1-flash-lite-preview"
FALLBACK_MODEL = "gemini-2.5-flash-lite"

CHUNK_MAX_CHARS = 1800  # 2000文字未満で余裕を持たせる


def _make_client() -> genai.Client:
    return genai.Client(api_key=os.environ["GEMINI_API_KEY"])


def _generate_with_model(model_name: str, research: dict) -> str:
    """指定モデルで台本を生成する。"""
    logger.info(f"Gemini ({model_name}) で台本生成中: {research['version']}")
    client = _make_client()

    prompt = f"""あなたはプロのPodcastスクリプトライターです。
以下の調査結果を元に、Claude Code {research['version']} について
5分程度（約2500〜3000文字）の日本語Podcastの台本を作成してください。

【調査結果】
{research['research_text'][:4000]}

【台本の要件】
- 出演者: ホスト「Airi（女性）」とゲスト「Kenji（男性）」の二人
- 形式: 自然な会話スタイル（堅くならず、技術的にも正確に）
- 構成: 冒頭の挨拶 → メイン解説 → ハイライト → まとめ・締め
- 各発言は1〜3文程度の自然な長さにする
- 専門用語は簡潔に説明を加える
- リスナーが楽しめるよう具体例や感想を交える

【出力フォーマット】必ず以下の形式で出力してください:
Airi: （セリフ）
Kenji: （セリフ）
Airi: （セリフ）
...

「Airi:」「Kenji:」以外のテキスト（説明文・ト書き・タイトルなど）は含めないでください。"""

    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
    )
    return response.text


def _generate_primary(research: dict) -> str:
    return _generate_with_model(PRIMARY_MODEL, research)


def _generate_fallback(research: dict) -> str:
    return _generate_with_model(FALLBACK_MODEL, research)


def parse_script(raw_text: str) -> list[dict]:
    """台本テキストを [{speaker, text}, ...] のリストに変換する。"""
    lines = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^(Airi|Kenji)\s*[:：]\s*(.+)$", line)
        if m:
            lines.append({"speaker": m.group(1), "text": m.group(2).strip()})
        else:
            # パースできない行は直前のスピーカーに追記（継続行）
            if lines:
                lines[-1]["text"] += "　" + line
    return lines


def split_into_chunks(lines: list[dict], max_chars: int = CHUNK_MAX_CHARS) -> list[list[dict]]:
    """台本をTTS用チャンクに分割する。

    各チャンクは max_chars 文字未満。発言の途中では切らない。
    """
    chunks = []
    current_chunk = []
    current_len = 0

    for line in lines:
        line_text = f"{line['speaker']}: {line['text']}\n"
        if current_len + len(line_text) > max_chars and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_len = 0
        current_chunk.append(line)
        current_len += len(line_text)

    if current_chunk:
        chunks.append(current_chunk)

    logger.info(f"台本を {len(chunks)} チャンクに分割しました")
    return chunks


def chunk_to_tts_text(chunk: list[dict]) -> str:
    """チャンクをTTS APIに渡すテキストに変換する。"""
    return "\n".join(f"{line['speaker']}: {line['text']}" for line in chunk)


def generate_script(research: dict) -> dict:
    """台本生成のメイン処理。結果をJSONに保存して返す。"""
    logger.info(f"=== 台本生成開始: {research['version']} ===")

    raw_text = retry_fallback_models(_generate_primary, _generate_fallback, research)
    lines = parse_script(raw_text)
    chunks = split_into_chunks(lines)

    total_chars = sum(len(line["text"]) for line in lines)
    logger.info(f"台本: {len(lines)} 発言, 合計 {total_chars} 文字, {len(chunks)} チャンク")

    result = {
        "version": research["version"],
        "target_date": research["target_date"],
        "raw_text": raw_text,
        "lines": lines,
        "chunks": [
            {
                "index": i,
                "tts_text": chunk_to_tts_text(chunk),
                "lines": chunk,
                "char_count": len(chunk_to_tts_text(chunk)),
            }
            for i, chunk in enumerate(chunks)
        ],
    }

    out_path = OUTPUT_DIR / f"{research['target_date']}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    logger.info(f"台本を保存しました: {out_path}")

    return result


if __name__ == "__main__":
    import sys

    research_file = sys.argv[1] if len(sys.argv) > 1 else None
    if research_file:
        with open(research_file, encoding="utf-8") as f:
            research = json.load(f)
    else:
        files = sorted((Path(__file__).parent.parent / "output" / "research").glob("*.json"))
        if not files:
            print("調査結果ファイルが見つかりません")
            sys.exit(1)
        with open(files[-1], encoding="utf-8") as f:
            research = json.load(f)

    result = generate_script(research)
    print(f"台本生成完了: {len(result['chunks'])} チャンク")
