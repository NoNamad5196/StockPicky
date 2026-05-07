# -*- coding: utf-8 -*-
"""순수 함수 기반 채점 모듈 — I/O 없음."""
from models import StockEvent

_TRUSTED_SOURCES = {"reuters.com", "bloomberg.com", "wsj.com", "ft.com", "cnbc.com", "apnews.com"}
_LOW_SOURCES = {"reddit.com", "twitter.com", "x.com", "stocktwits.com"}

_NEWS_POSITIVE_KEYWORDS = {
    "beat", "record", "surge", "rally", "upgrade", "buy", "strong",
    "profit", "growth", "partnership", "approval", "breakthrough",
}
_NEWS_NEGATIVE_KEYWORDS = {
    "miss", "loss", "decline", "cut", "downgrade", "sell", "layoff",
    "recall", "lawsuit", "fraud", "warning", "crash", "investigation",
}


def _credibility(source: str) -> int:
    lower = source.lower()
    for domain in _TRUSTED_SOURCES:
        if domain in lower:
            return 5
    for domain in _LOW_SOURCES:
        if domain in lower:
            return 1
    return 3


def _sentiment_from_text(text: str) -> str:
    lower = text.lower()
    pos = sum(1 for kw in _NEWS_POSITIVE_KEYWORDS if kw in lower)
    neg = sum(1 for kw in _NEWS_NEGATIVE_KEYWORDS if kw in lower)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


def _alert_level(impact: int, urgency: int) -> int:
    if impact >= 4 and urgency >= 4:
        return 5
    if impact >= 3 and urgency >= 3:
        return 4
    if impact >= 2:
        return 3
    if impact >= 1:
        return 2
    return 1


def score_price_event(event: StockEvent, pct: float) -> StockEvent:
    abs_pct = abs(pct)

    if abs_pct < 0.1:
        event.alert_level = 1
        event.should_alert = False
        return event

    if abs_pct >= 5.0:
        event.market_impact_score = 5
        event.urgency_score = 5
    elif abs_pct >= 3.0:
        event.market_impact_score = 4
        event.urgency_score = 4
    else:
        event.market_impact_score = 2
        event.urgency_score = 2

    event.credibility_score = 5
    event.sentiment = "positive" if pct > 0 else "negative"
    event.alert_level = _alert_level(event.market_impact_score, event.urgency_score)
    event.should_alert = event.alert_level >= 4

    stars_impact = "⭐" * event.market_impact_score + "☆" * (5 - event.market_impact_score)
    stars_urgency = "⭐" * event.urgency_score + "☆" * (5 - event.urgency_score)

    if pct > 0:
        event.headline_mood = f"쪼아요 쪼아요 {event.ticker} 위로 쪼아요! +{pct:.1f}%"
        event.reason = [f"{event.ticker} {pct:+.1f}% 급등 감지"]
    else:
        event.headline_mood = f"으아앙 {event.ticker} 아래로 네르지 마세요! {pct:.1f}%"
        event.reason = [f"{event.ticker} {pct:+.1f}% 급락 감지"]

    event.risk_note = "과거 데이터 기반 알림이에요. 투자는 신중하게 해요!"
    return event


def score_news_event(event: StockEvent) -> StockEvent:
    event.credibility_score = _credibility(event.source)
    event.sentiment = _sentiment_from_text(event.title + " " + event.summary)

    if event.credibility_score >= 5:
        event.market_impact_score = 3
        event.urgency_score = 3
    elif event.credibility_score >= 3:
        event.market_impact_score = 2
        event.urgency_score = 2
    else:
        event.market_impact_score = 1
        event.urgency_score = 1

    if event.sentiment != "neutral":
        event.market_impact_score = min(5, event.market_impact_score + 1)

    event.alert_level = _alert_level(event.market_impact_score, event.urgency_score)
    event.should_alert = event.alert_level >= 4

    if event.sentiment == "positive":
        event.headline_mood = f"쪼아요 쪼아요 {event.ticker} 호재 쪼아요!"
    elif event.sentiment == "negative":
        event.headline_mood = f"으아앙 {event.ticker} 주식 네르지 마세요!"
    else:
        event.headline_mood = f"웅성웅성 {event.ticker} 소문이에요!"

    event.reason = [event.title]
    event.risk_note = "뉴스 기반 알림이에요. 직접 확인해줘요!"
    return event


def score(event: StockEvent, pct: float = 0.0) -> StockEvent:
    if event.event_type == "price_spike":
        return score_price_event(event, pct)
    return score_news_event(event)
