"""音声生成モジュール

Gemini 3.1 Flash TTS Preview でマルチスピーカー音声を生成する。
チャンクごとにPCMデータを取得し、WAVファイルとして保存する。

- Airi (女性): Kore
- Kenji (男性): Puck
フォールバックモデル: gemini-2.5-flash-tts
"""

import json
import os
import struct
import time
from pathlib import Path

from google import genai
from google.genai import types

from utils import logger, retry_fallback_models

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "audio"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

PRIMARY_TTS_MODEL = "gemini-3.1-flash-tts-preview"
FALLBACK_TTS_MODEL = "gemini-2.5-flash-tts"

SAMPLE_RATE = 24000
CHANNELS = 1
BITS_PER_SAMPLE = 16

# RPM制限対策: チャンク間の待機秒数
CHUNK_WAIT_SEC = 8


def pcm_to_wav(pcm_data: bytes, sample_rate: int = SAMPLE_RATE) -> bytes:
    """PCMバイト列にWAVヘッダーを付与してWAVバイト列を返す。"""
    byte_rate = sample_rate * CHANNELS * BITS_PER_SAMPLE // 8
    block_align = CHANNELS * BITS_PER_SAMPLE // 8
    data_size = len(pcm_data)
    chunk_size = 36 + data_size

    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        chunk_size,
        b"WAVE",
        b"fmt ",
        16,             # Subchunk1Size (PCM)
        1,              # AudioFormat (PCM)
        CHANNELS,
        sample_rate,
        byte_rate,
        block_align,
        BITS_PER_SAMPLE,
        b"data",
        data_size,
    )
    return header + pcm_data


def _call_tts(model_name: str, tts_text: str) -> bytes:
    """指定モデルでTTSを呼び出し、PCMバイト列を返す。"""
    logger.info(f"TTS ({model_name}): {len(tts_text)} 文字を変換中...")
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    response = client.models.generate_content(
        model=model_name,
        contents=tts_text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                    speaker_voice_configs=[
                        types.SpeakerVoiceConfig(
                            speaker="Airi",
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name="Kore"
                                )
                            ),
                        ),
                        types.SpeakerVoiceConfig(
                            speaker="Kenji",
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name="Puck"
                                )
                            ),
                        ),
                    ]
                )
            ),
        ),
    )

    # レスポンスからPCMデータを取得
    part = response.candidates[0].content.parts[0]
    if part.inline_data and part.inline_data.data:
        import base64
        pcm_data = base64.b64decode(part.inline_data.data)
        logger.info(f"PCMデータ取得: {len(pcm_data)} バイト ({len(pcm_data)/SAMPLE_RATE/2:.1f}秒)")
        return pcm_data

    raise ValueError("TTS レスポンスに音声データが含まれていません")


def _tts_primary(tts_text: str) -> bytes:
    return _call_tts(PRIMARY_TTS_MODEL, tts_text)


def _tts_fallback(tts_text: str) -> bytes:
    return _call_tts(FALLBACK_TTS_MODEL, tts_text)


def generate_audio_chunks(script: dict) -> list[Path]:
    """台本の全チャンクを音声化し、WAVファイルのリストを返す。"""
    logger.info(f"=== 音声生成開始: {script['version']} ({len(script['chunks'])} チャンク) ===")
    date = script["target_date"]
    audio_dir = OUTPUT_DIR / date
    audio_dir.mkdir(parents=True, exist_ok=True)

    wav_paths = []

    for chunk in script["chunks"]:
        idx = chunk["index"]
        tts_text = chunk["tts_text"]
        out_path = audio_dir / f"chunk_{idx:03d}.wav"

        if out_path.exists():
            logger.info(f"チャンク {idx} は既に生成済みです。スキップ: {out_path}")
            wav_paths.append(out_path)
            continue

        logger.info(
            f"チャンク {idx}/{len(script['chunks']) - 1} を生成中 ({chunk['char_count']} 文字)..."
        )
        pcm_data = retry_fallback_models(_tts_primary, _tts_fallback, tts_text)
        wav_data = pcm_to_wav(pcm_data)

        with open(out_path, "wb") as f:
            f.write(wav_data)
        logger.info(f"WAV保存: {out_path} ({len(wav_data)} バイト)")
        wav_paths.append(out_path)

        # RPM制限対策: 最後のチャンク以外は待機
        if idx < len(script["chunks"]) - 1:
            logger.info(f"RPM制限対策: {CHUNK_WAIT_SEC}秒待機...")
            time.sleep(CHUNK_WAIT_SEC)

    logger.info(f"音声生成完了: {len(wav_paths)} ファイル")
    return wav_paths


if __name__ == "__main__":
    import sys

    script_file = sys.argv[1] if len(sys.argv) > 1 else None
    if script_file:
        with open(script_file, encoding="utf-8") as f:
            script = json.load(f)
    else:
        files = sorted((Path(__file__).parent.parent / "output" / "scripts").glob("*.json"))
        if not files:
            print("台本ファイルが見つかりません")
            sys.exit(1)
        with open(files[-1], encoding="utf-8") as f:
            script = json.load(f)

    paths = generate_audio_chunks(script)
    print(f"音声生成完了: {[str(p) for p in paths]}")
