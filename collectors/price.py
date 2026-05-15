# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timezone, timedelta
from datetime import time as dt_time
from typing import Optional

import yfinance as yf

from models import StockEvent
from scorer import score_price_event

logger = logging.getLogger(__name__)


_KST = timezone(timedelta(hours=9))


def _is_index(ticker: str) -> bool:
    return ticker.startswith("^")


def _is_kr_market_open() -> bool:
    """KRX 정규 장 시간(월~금 09:00~15:30 KST) 여부 확인."""
    now = datetime.now(_KST)
    if now.weekday() >= 5:              # 토/일 휴장
        return False
    t = now.time()
    return dt_time(9, 0) <= t <= dt_time(19, 0)


def _is_fx(ticker: str) -> bool:
    return ticker.upper().endswith("=X")


def _resolve_ticker(ticker: str, market: str) -> str:
    """yfinance용 티커 변환."""
    if market == "FX":
        return ticker               # USDKRW=X 등 그대로
    if market == "KR":
        if _is_index(ticker):
            return ticker           # ^KS11, ^KQ11 → 그대로
        if "." not in ticker:
            return f"{ticker}.KS"  # KOSPI 우선 시도
    return ticker


def _fetch_price(yt: str) -> tuple[Optional[float], Optional[float]]:
    """(last_price, previous_close) 반환. 실패 시 (None, None)."""
    try:
        info = yf.Ticker(yt).fast_info
        return info.last_price, info.previous_close
    except Exception:
        return None, None


def collect_price(ticker: str, market: str = "US") -> Optional[StockEvent]:
    # KR 개별 종목은 장 시간(09:00~15:30 KST) 외에는 데이터 의미 없음 → 스킵
    if market == "KR" and not _is_index(ticker) and not _is_kr_market_open():
        logger.debug("KR 장 마감 — 수집 스킵: %s", ticker)
        return None

    yt = _resolve_ticker(ticker, market)
    last, prev = _fetch_price(yt)

    # KOSPI(.KS) 실패 시 KOSDAQ(.KQ) 재시도
    if market == "KR" and not _is_index(ticker) and (last is None) and yt.endswith(".KS"):
        yt_kq = yt.replace(".KS", ".KQ")
        logger.debug("%s .KS 실패 → .KQ 재시도", ticker)
        last, prev = _fetch_price(yt_kq)
        if last is not None:
            yt = yt_kq

    if last is None or prev is None or prev == 0:
        logger.warning("가격 데이터 없음: %s", yt)
        return None

    pct = (last - prev) / prev * 100
    is_idx = _is_index(ticker)
    is_fx_ticker = _is_fx(ticker)
    is_kr_stock = (market == "KR") and not is_idx and not is_fx_ticker

    # 지수/환율은 낮은 임계값 적용
    noise_floor = 0.05 if (is_idx or is_fx_ticker) else 0.1
    if abs(pct) < noise_floor:
        return None

    event = StockEvent(
        ticker=ticker,
        event_type="price_spike",
        title=f"{ticker} {pct:+.2f}% 변동",
        summary=f"{ticker} 현재가 {last:.4f}, 전일 대비 {pct:+.2f}%",
        source="yfinance",
    )
    return score_price_event(event, pct, is_index=is_idx, is_fx=is_fx_ticker, is_kr=is_kr_stock)


def fetch_ticker_name(ticker: str, market: str) -> str:
    """yfinance에서 회사명 조회. 실패 시 빈 문자열 반환."""
    yt = _resolve_ticker(ticker, market)
    candidates = [yt]
    if yt.endswith(".KS"):
        candidates.append(yt.replace(".KS", ".KQ"))
    for yt_try in candidates:
        try:
            info = yf.Ticker(yt_try).info
            name = info.get("shortName") or info.get("longName", "")
            if name:
                return name.strip()
        except Exception:
            continue
    return ""


def collect_all_prices(tickers: list[dict]) -> list[StockEvent]:
    events = []
    for row in tickers:
        result = collect_price(row["ticker"], row.get("market", "US"))
        if result is not None:
            events.append(result)
    return events
