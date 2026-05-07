# -*- coding: utf-8 -*-
import logging
from typing import Optional

import yfinance as yf

from models import StockEvent
from scorer import score_price_event

logger = logging.getLogger(__name__)


def _is_index(ticker: str) -> bool:
    return ticker.startswith("^")


def _resolve_ticker(ticker: str, market: str) -> str:
    """yfinance용 티커 변환. KR 지수는 그대로, 일반 KR 종목은 .KS 시도."""
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

    # 지수는 낮은 임계값 적용 (0.1% 노이즈 필터)
    noise_floor = 0.05 if is_idx else 0.1
    if abs(pct) < noise_floor:
        return None

    event = StockEvent(
        ticker=ticker,
        event_type="price_spike",
        title=f"{ticker} {pct:+.2f}% 변동",
        summary=f"{ticker} 현재가 {last:.2f}, 전일 대비 {pct:+.2f}%",
        source="yfinance",
    )
    return score_price_event(event, pct, is_index=is_idx)


def collect_all_prices(tickers: list[dict]) -> list[StockEvent]:
    events = []
    for row in tickers:
        result = collect_price(row["ticker"], row.get("market", "US"))
        if result is not None:
            events.append(result)
    return events
