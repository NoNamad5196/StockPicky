# -*- coding: utf-8 -*-
"""
규칙 기반 스톡피키 말투 Discord embed dict 생성.

커스텀 이모지 사용 규칙:
  :jjowayo:   호재/급등/긍정 → 제목, 본문 첫 줄
  :uaaang:    악재/급락/부정 → 제목, 본문 첫 줄
  :ggang:     대형 이벤트(Level 5) 강조
  :yolsimhi:  모니터링/브리핑 헤더/열심히 문구
"""
from datetime import datetime, timezone, timedelta
from models import StockEvent
import emojis as em

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


def _headline(event: StockEvent) -> str:
    """이벤트 타입 + 감정에 따른 제목 문구 (커스텀 이모지 포함)."""
    t = event.ticker
    key = (event.event_type, event.sentiment)

    if key == ("price_spike", "positive"):
        level_badge = f" {em.ggang()}" if event.alert_level == 5 else ""
        return f"{em.jjowayo(2)} {t} 위로 쪼아요! {_pct_from_title(event.title)}%{level_badge}"

    if key == ("price_spike", "negative"):
        level_badge = f" {em.ggang()}" if event.alert_level == 5 else ""
        return f"{em.uaaang(2)} {t} 아래로 네르지 마세요!{level_badge}"

    if key == ("news", "positive"):
        return f"{em.jjowayo()} {t} 호재 소식이에요!"

    if key == ("news", "negative"):
        return f"{em.uaaang()} {t} 악재 소식이에요!"

    return f"{em.yolsimhi()} {t} 소문이에요! 웅성웅성"


def _pct_from_title(title: str) -> str:
    """title에서 등락률 숫자만 추출 (없으면 빈 문자열)."""
    import re
    m = re.search(r"([+-]?\d+\.?\d*)\s*%", title)
    return m.group(1) if m else "?"


def _opening(event: StockEvent) -> str:
    """본문 첫 줄 감성 문구."""
    if event.sentiment == "positive":
        return f"{em.jjowayo()} 스톡피키 좋은 소식 가져왔어요!"
    if event.sentiment == "negative":
        return f"{em.uaaang()} 스톡피키 걱정되는 소식이에요..."
    return f"{em.yolsimhi()} 스톡피키 열심히 봤어요!"


def format_alert(event: StockEvent) -> dict:
    now_str = datetime.now(KST).strftime("%Y-%m-%d %H:%M KST")

    reason_lines = "\n".join(f"• {r}" for r in event.reason) if event.reason else "• 수집된 정보 기반이에요."

    description = (
        f"{_opening(event)}\n"
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
        "title": _headline(event),  # 항상 이모지 데코 버전 사용
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
            f"{em.ggang()} **{e['ticker']}** — {e.get('headline_mood') or e.get('title', '')}"
            for e in level5
        )
        sections.append(f"**⚡ 긴급 이벤트**\n{lines}")

    if level4:
        lines = "\n".join(
            f"{em.uaaang() if _is_negative(e) else em.jjowayo()} **{e['ticker']}** — {e.get('headline_mood') or e.get('title', '')}"
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
        body = f"{em.yolsimhi()} 오늘은 특별한 소식이 없었어요. 스톡피키 열심히 지켜봤는데 조용하네요!"
    else:
        body = "\n\n".join(sections)

    description = (
        f"{em.yolsimhi()} 스톡피키 오늘 하루도 열심히 봤어요!\n\n"
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


def _is_negative(event_dict: dict) -> bool:
    return event_dict.get("sentiment") == "negative"
