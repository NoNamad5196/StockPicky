# -*- coding: utf-8 -*-
import html
import logging
import re
import time
import urllib.parse
from typing import Optional

import feedparser

from models import StockEvent
from scorer import score_news_event

logger = logging.getLogger(__name__)

_GNEWS_BASE = "https://news.google.com/rss/search"
_HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; StockPicky/1.0)"}
_MAX_ITEMS  = 5


def _build_url(query: str, hl: str, gl: str, ceid: str) -> str:
    """Google News RSS URL — urllib.parse.urlencode으로 한글/공백 안전하게 인코딩."""
    params = urllib.parse.urlencode({"q": query, "hl": hl, "gl": gl, "ceid": ceid})
    return f"{_GNEWS_BASE}?{params}"


def _strip_html(text: str) -> str:
    """HTML 태그 제거 + 엔티티 디코딩 + 공백 정리."""
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return " ".join(text.split())


def _entry_published(entry) -> str:
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            return time.strftime("%Y-%m-%dT%H:%M:%S", entry.published_parsed)
        except Exception:
            pass
    return ""


def _fetch_feed(url: str, ticker: str):
    """feedparser 호출.
    bozo(경미한 XML 오류)여도 entries가 있으면 계속 진행.
    Google News RSS는 bozo가 자주 켜지지만 실제 파싱은 정상인 경우가 많음.
    """
    try:
        feed = feedparser.parse(url, request_headers=_HEADERS)
    except Exception as e:
        logger.warning("뉴스 RSS 요청 실패 (%s): %s", ticker, e)
        return None

    if feed.bozo:
        if feed.entries:
            # 경미한 XML 오류지만 항목은 있음 → 무시하고 계속
            logger.debug("RSS bozo 무시 (entries=%d) (%s): %s",
                         len(feed.entries), ticker, feed.bozo_exception)
        else:
            # 항목도 없으면 진짜 오류
            logger.warning("RSS bozo + 빈 feed (%s): %s", ticker, feed.bozo_exception)
            return None

    return feed


def collect_news(ticker: str, market: str = "US", name: str = "") -> list[StockEvent]:
    if market == "KR":
        # 종목코드(예: 005930) + 회사명 조합으로 검색
        # → 한국어 뉴스 RSS에서 적중률 높임
        query = f"{ticker} {name}".strip() if name else ticker
        url = _build_url(query, hl="ko-KR", gl="KR", ceid="KR:ko")
    elif market == "FX":
        query = f"{ticker} 환율"
        url = _build_url(query, hl="ko-KR", gl="KR", ceid="KR:ko")
    else:
        url = _build_url(f"{ticker} stock", hl="en-US", gl="US", ceid="US:en")

    logger.debug("뉴스 RSS 요청: %s → %s", ticker, url)

    feed = _fetch_feed(url, ticker)
    if feed is None or not feed.entries:
        logger.debug("뉴스 없음: %s", ticker)
        return []

    events = []
    for entry in feed.entries[:_MAX_ITEMS]:
        title      = _strip_html(getattr(entry, "title", ""))
        source     = getattr(entry, "source", {})
        source_name = source.get("title", "") if isinstance(source, dict) else str(source)
        link       = getattr(entry, "link", "")
        summary_raw = _strip_html(getattr(entry, "summary", title))

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

    logger.debug("뉴스 수집 완료: %s → %d건", ticker, len(events))
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
