"""リトライ・ログユーティリティ"""

import time
import logging
import functools
from datetime import datetime, timezone, timedelta

JST = timezone(timedelta(hours=9))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def jst_now() -> datetime:
    return datetime.now(JST)


def jst_today_str() -> str:
    return jst_now().strftime("%Y-%m-%d")


def jst_yesterday_str() -> str:
    return (jst_now() - timedelta(days=1)).strftime("%Y-%m-%d")


def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 60.0,
    fallback=None,
):
    """指数バックオフでリトライ。全リトライ失敗時は fallback 関数を呼ぶ。"""
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    wait = base_delay * (2 ** attempt)
                    logger.warning(
                        f"{func.__name__} 失敗 (試行 {attempt + 1}/{max_retries}): {e}  "
                        f"{wait:.0f}秒後にリトライします"
                    )
                    if attempt < max_retries - 1:
                        time.sleep(wait)

            logger.error(f"{func.__name__} が {max_retries} 回失敗しました: {last_exc}")

            if fallback is not None:
                logger.info(f"フォールバック関数を実行します: {fallback.__name__}")
                return fallback(*args, **kwargs)

            raise last_exc

        return wrapper
    return decorator


def retry_fallback_models(primary_func, fallback_func, *args, **kwargs):
    """プライマリAPIを3回試みて失敗したらフォールバックAPIを呼ぶ。"""
    max_retries = 3
    last_exc = None

    for attempt in range(max_retries):
        try:
            return primary_func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            wait = 60.0 * (2 ** attempt)
            logger.warning(
                f"プライマリAPI失敗 (試行 {attempt + 1}/{max_retries}): {e}  "
                f"{wait:.0f}秒後にリトライ"
            )
            if attempt < max_retries - 1:
                time.sleep(wait)

    logger.warning(f"プライマリAPIが全失敗。フォールバックAPIを試みます: {last_exc}")

    for attempt in range(max_retries):
        try:
            return fallback_func(*args, **kwargs)
        except Exception as e:
            last_exc = e
            wait = 60.0 * (2 ** attempt)
            logger.warning(
                f"フォールバックAPI失敗 (試行 {attempt + 1}/{max_retries}): {e}  "
                f"{wait:.0f}秒後にリトライ"
            )
            if attempt < max_retries - 1:
                time.sleep(wait)

    raise RuntimeError(f"プライマリ・フォールバック両方のAPIが失敗しました: {last_exc}")
