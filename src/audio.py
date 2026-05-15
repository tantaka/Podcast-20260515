"""音声処理モジュール

WAVチャンクを結合してMP3に変換する。
pydub + FFmpeg を使用。
"""

import struct
from pathlib import Path

from pydub import AudioSegment

from utils import logger

OUTPUT_DIR = Path(__file__).parent.parent / "output" / "audio"


def concat_wav_files(wav_paths: list[Path]) -> AudioSegment:
    """複数のWAVファイルを結合してAudioSegmentを返す。"""
    logger.info(f"WAVファイルを結合中: {len(wav_paths)} ファイル")
    if not wav_paths:
        raise ValueError("結合するWAVファイルがありません")

    combined = AudioSegment.from_wav(str(wav_paths[0]))
    for path in wav_paths[1:]:
        seg = AudioSegment.from_wav(str(path))
        combined += seg
        logger.info(f"  結合: {path.name} (累計 {len(combined) / 1000:.1f}秒)")

    logger.info(f"結合完了: 合計 {len(combined) / 1000:.1f}秒")
    return combined


def export_mp3(audio: AudioSegment, output_path: Path, bitrate: str = "128k") -> Path:
    """AudioSegmentをMP3ファイルとして書き出す。"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    audio.export(str(output_path), format="mp3", bitrate=bitrate)
    size_kb = output_path.stat().st_size // 1024
    logger.info(f"MP3書き出し完了: {output_path} ({size_kb} KB)")
    return output_path


def process_audio(wav_paths: list[Path], date: str, version: str) -> Path:
    """WAVチャンクをMP3に変換するメイン処理。"""
    logger.info(f"=== 音声変換開始: {version} ===")
    combined = concat_wav_files(wav_paths)
    mp3_path = OUTPUT_DIR / date / "podcast.mp3"
    export_mp3(combined, mp3_path)
    return mp3_path


if __name__ == "__main__":
    import sys

    date_arg = sys.argv[1] if len(sys.argv) > 1 else None
    if not date_arg:
        dirs = sorted((OUTPUT_DIR).glob("????-??-??"))
        if not dirs:
            print("音声ディレクトリが見つかりません")
            sys.exit(1)
        date_arg = dirs[-1].name

    audio_dir = OUTPUT_DIR / date_arg
    wav_files = sorted(audio_dir.glob("chunk_*.wav"))
    if not wav_files:
        print(f"WAVファイルが見つかりません: {audio_dir}")
        sys.exit(1)

    mp3 = process_audio(wav_files, date_arg, date_arg)
    print(f"MP3変換完了: {mp3}")
