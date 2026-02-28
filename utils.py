"""
============================================================
END NF 콘텐츠 시스템 - 유틸리티
============================================================
재시도, 에러 핸들링, 공통 함수
"""

import time
import functools
import logging

logger = logging.getLogger("endnf")


def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions=(Exception,)):
    """
    함수 재시도 데코레이터

    Args:
        max_retries: 최대 재시도 횟수
        delay: 초기 대기 시간 (초)
        backoff: 대기 시간 배수
        exceptions: 재시도할 예외 타입

    사용법:
        @retry(max_retries=3, delay=1)
        def fetch_data():
            ...
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    if attempt == max_retries:
                        logger.error(f"❌ {func.__name__}: {max_retries}회 재시도 후 최종 실패: {e}")
                        raise
                    logger.warning(
                        f"⚠️ {func.__name__}: 시도 {attempt+1}/{max_retries} 실패 ({e}). "
                        f"{current_delay:.1f}초 후 재시도..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
        return wrapper
    return decorator


def truncate_text(text: str, max_length: int = 500, suffix: str = "...") -> str:
    """텍스트를 최대 길이로 자르기"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def safe_get(data: dict, *keys, default=None):
    """중첩 딕셔너리에서 안전하게 값 가져오기"""
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            return default
    return current


def format_date_kr(date_str: str) -> str:
    """다양한 날짜 형식을 한국어 형식으로 변환"""
    from datetime import datetime

    formats = [
        "%Y-%m-%d",
        "%Y/%m/%d",
        "%Y %b %d",
        "%Y %b",
        "%Y",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str.strip(), fmt)
            return dt.strftime("%Y년 %m월 %d일")
        except ValueError:
            continue

    return date_str  # 변환 실패 시 원본 반환
