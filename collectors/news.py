# -*- coding: utf-8 -*-
import hashlib
import logging
import time
from typing import Optional

import feedparser

from models import StockEvent
from scorer import score_news_event

logger = logging.getLogger(__name__)

_RSS_US = (
    "https://news.google.com/rss/search?q={query}+stock"
    "&hl=en-US&gl=US&ceid=US:en"
)
_RSS_KR = (
    "https://news.google.com/rss/search?q={query}+주식"
    "&hl=ko-KR&gl=KR&ceid=KR:ko"
)
_MAX_ITEMS = 5


def _entry_published(entry) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return time.strftime("%Y-%m-%dT%H:%M:%S", entry.published_parsed)
        except Exception:
            pass
    return ""


def collect_news(ticker: str, market: str = "US", name: str = "") -> list[StockEvent]:
    # KR 종목은 회사명으로 한국어 검색, 없으면 ticker로 영어 검색
    if market == "KR":
        query = name if name else ticker
        url = _RSS_KR.format(query=query)
    else:
        url = _RSS_US.format(query=ticker)

    try:
        feed = feedparser.parse(url)
    except Exception as e:
        logger.warning("뉴스 파싱 오류 (%s): %s", ticker, e)
        return []

    if feed.bozo:
        logger.warning("뉴스 RSS 오류 (%s): %s", ticker, feed.bozo_exception)
        return []

    events = []
    for entry in feed.entries[:_MAX_ITEMS]:
        title = getattr(entry, "title", "")
        source = getattr(entry, "source", {})
        source_name = source.get("title", "") if isinstance(source, dict) else str(source)
        link = getattr(entry, "link", "")
        summary_raw = getattr(entry, "summary", title)

        if not title:
            continue

        event = StockEvent(
            ticker=ticker,
            event_type="news",
            title=title,
            summary=summary_raw[:500],
            source=source_name or "Google News",
            url=link,
            collected_at=_entry_published(entry) or "",
        )
        event = score_news_event(event)
        events.append(event)

    return events


def collect_all_news(tickers: list[dict]) -> list[StockEvent]:
    all_events = []
    for row in tickers:
        ticker = row["ticker"]
        market = row.get("market", "US")
        name   = row.get("name", "")
        try:
            news = collect_news(ticker, market, name)
            all_events.extend(news)
        except Exception as e:
            logger.warning("뉴스 수집 실패 (%s): %s", ticker, e)
    return all_events
