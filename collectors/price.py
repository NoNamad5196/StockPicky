# -*- coding: utf-8 -*-
import logging
from typing import Optional

import yfinance as yf

from models import StockEvent
from scorer import score_price_event

logger = logging.getLogger(__name__)


def _resolve_ticker(ticker: str, market: str) -> str:
    """KR 종목에 .KS 접미사 추가."""
    if market == "KR" and "." not in ticker:
        return f"{ticker}.KS"
    return ticker


def collect_price(ticker: str, market: str = "US") -> Optional[StockEvent]:
    yt = _resolve_ticker(ticker, market)
    try:
        info = yf.Ticker(yt).fast_info
        last = info.last_price
        prev = info.previous_close

        if last is None or prev is None or prev == 0:
            logger.warning("가격 데이터 없음: %s", yt)
            return None

        pct = (last - prev) / prev * 100

        if abs(pct) < 0.1:
            return None

        event = StockEvent(
            ticker=ticker,
            event_type="price_spike",
            title=f"{ticker} {pct:+.2f}% 변동",
            summary=f"{ticker} 현재가 {last:.2f}, 전일 대비 {pct:+.2f}%",
            source="yfinance",
        )
        return score_price_event(event, pct)

    except Exception as e:
        logger.warning("주가 수집 실패 (%s): %s", yt, e)
        return None


def collect_all_prices(tickers: list[dict]) -> list[StockEvent]:
    events = []
    for row in tickers:
        result = collect_price(row["ticker"], row.get("market", "US"))
        if result is not None:
            events.append(result)
    return events
