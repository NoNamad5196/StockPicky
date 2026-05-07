# -*- coding: utf-8 -*-
"""규칙 기반 스톡피키 말투 Discord embed dict 생성 — LLM 없음."""
from datetime import datetime, timezone, timedelta
from models import StockEvent

KST = timezone(timedelta(hours=9))

_COLOR_POSITIVE = 0x00b894
_COLOR_NEGATIVE = 0xe17055
_COLOR_NEUTRAL  = 0x636e72


def _stars(score: int) -> str:
    return "⭐" * score + "☆" * (5 - score)


def _color(sentiment: str) -> int:
    if sentiment == "positive":
        return _COLOR_POSITIVE
    if sentiment == "negative":
        return _COLOR_NEGATIVE
    return _COLOR_NEUTRAL


def _opening_line(event: StockEvent) -> str:
    key = (event.event_type, event.sentiment)
    dispatch = {
        ("price_spike", "positive"): f"쪼아요 쪼아요 {event.ticker} 위로 쪼아요!",
        ("price_spike", "negative"): f"으아앙 {event.ticker} 아래로 네르지 마세요!",
        ("news", "positive"):        f"쪼아요 쪼아요 {event.ticker} 호재 쪼아요!",
        ("news", "negative"):        f"으아앙 {event.ticker} 주식 네르지 마세요!",
    }
    return dispatch.get(key, f"웅성웅성 {event.ticker} 소문이에요!")


def format_alert(event: StockEvent) -> dict:
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")
    opening = _opening_line(event)

    reason_lines = "\n".join(f"• {r}" for r in event.reason) if event.reason else "• 수집된 정보 기반이에요."

    description = (
        f"스톡피키... 열심히 봤는데...\n"
        f"{event.summary}\n"
        f"스톡피키 바보 아니란 말이에요!\n\n"
        f"중요도: {_stars(event.market_impact_score)} | "
        f"긴급도: {_stars(event.urgency_score)} | "
        f"신뢰도: {_stars(event.credibility_score)}\n\n"
        f"왜 봐야 해요?\n{reason_lines}\n\n"
        f"⚠️ 쪼아요라고 했지 매수하라는 뜻은 아니에요!"
    )

    if event.url:
        description += f"\n\n🔗 [원문 보러가기]({event.url})"

    return {
        "color": _color(event.sentiment),
        "title": event.headline_mood or opening,
        "description": description,
        "footer": f"스톡피키 | {event.ticker} | {now_str}",
    }


def format_daily_briefing(events: list[dict]) -> dict:
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    level5 = [e for e in events if e.get("alert_level") == 5]
    level4 = [e for e in events if e.get("alert_level") == 4]
    level3 = [e for e in events if e.get("alert_level") == 3]

    sections = []

    if level5:
        lines = "\n".join(
            f"🚨 **{e['ticker']}** — {e.get('headline_mood') or e.get('title', '')}"
            for e in level5
        )
        sections.append(f"**⚡ 긴급 이벤트**\n{lines}")

    if level4:
        lines = "\n".join(
            f"🔔 **{e['ticker']}** — {e.get('headline_mood') or e.get('title', '')}"
            for e in level4
        )
        sections.append(f"**📢 주요 이벤트**\n{lines}")

    if level3:
        lines = "\n".join(
            f"📌 **{e['ticker']}** — {e.get('headline_mood') or e.get('title', '')}"
            for e in level3
        )
        sections.append(f"**📋 일반 이벤트**\n{lines}")

    if not sections:
        body = "오늘은 특별한 소식이 없었어요. 스톡피키 열심히 지켜봤는데 조용하네요!"
    else:
        body = "\n\n".join(sections)

    description = (
        f"스톡피키 오늘 하루도 열심히 봤어요!\n\n"
        f"{body}\n\n"
        f"⚠️ 쪼아요라고 했지 매수하라는 뜻은 아니에요!"
    )

    total = len(events)
    return {
        "color": _COLOR_NEUTRAL,
        "title": f"📊 스톡피키 하루 정리글 — 이벤트 {total}건이에요!",
        "description": description,
        "footer": f"스톡피키 데일리 브리핑 | {now_str}",
    }
