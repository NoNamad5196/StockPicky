# -*- coding: utf-8 -*-
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def _now_kst() -> str:
    return datetime.now(KST).isoformat()


@dataclass
class StockEvent:
    ticker: str
    event_type: str          # "price_spike" | "news" | "volume_surge"
    title: str
    summary: str
    source: str
    url: str = ""
    sentiment: str = "neutral"       # "positive" | "negative" | "neutral"
    market_impact_score: int = 0     # 1~5
    urgency_score: int = 0           # 1~5
    credibility_score: int = 0       # 1~5
    alert_level: int = 0             # 1~5
    should_alert: bool = False
    headline_mood: str = ""
    reason: list = field(default_factory=list)
    risk_note: str = ""
    collected_at: str = field(default_factory=_now_kst)
