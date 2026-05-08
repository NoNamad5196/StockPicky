# -*- coding: utf-8 -*-
"""순수 함수 기반 채점 모듈 — I/O 없음."""
from models import StockEvent

_TRUSTED_SOURCES = {
    # 미국/글로벌
    "reuters.com", "bloomberg.com", "wsj.com", "ft.com",
    "cnbc.com", "apnews.com", "investing.com",
    # 한국
    "hankyung.com", "mk.co.kr", "yna.co.kr", "edaily.co.kr",
    "biz.chosun.com", "newsis.com", "sedaily.com",
}
_LOW_SOURCES = {"reddit.com", "twitter.com", "x.com", "stocktwits.com"}

_NEWS_POSITIVE_KEYWORDS = {
    # 영어
    "beat", "record", "surge", "rally", "upgrade", "buy", "strong",
    "profit", "growth", "partnership", "approval", "breakthrough",
    # 한국어
    "호재", "실적개선", "신고가", "강세", "상승", "흑자",
    "수주", "승인", "급등", "매수",
}
_NEWS_NEGATIVE_KEYWORDS = {
    # 영어
    "miss", "loss", "decline", "cut", "downgrade", "sell", "layoff",
    "recall", "lawsuit", "fraud", "warning", "crash", "investigation",
    # 한국어
    "악재", "실적부진", "신저가", "약세", "하락", "적자",
    "취소", "리콜", "조사", "제재", "급락", "매도",
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
    pos = sum(1 for kw in _NEWS_POSITIVE_KEYWORDS if kw in text)
    neg = sum(1 for kw in _NEWS_NEGATIVE_KEYWORDS if kw in text)
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


def score_price_event(
    event: StockEvent, pct: float, is_index: bool = False, is_fx: bool = False
) -> StockEvent:
    abs_pct = abs(pct)

    if is_index or is_fx:
        # 지수/환율: 작은 % 변동도 의미 있음
        if abs_pct >= 2.0:
            event.market_impact_score = 5
            event.urgency_score = 5
        elif abs_pct >= 1.0:
            event.market_impact_score = 4
            event.urgency_score = 4
        elif abs_pct >= 0.5:
            event.market_impact_score = 3
            event.urgency_score = 3
        else:
            event.market_impact_score = 2
            event.urgency_score = 2
    else:
        # 개별 종목
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

    if is_fx:
        label = "환율"
        up_reason   = "환율 상승"
        down_reason = "환율 하락"
    elif is_index:
        label = "지수"
        up_reason   = "지수 상승"
        down_reason = "지수 하락"
    else:
        label = ""
        up_reason   = "급등"
        down_reason = "급락"

    # 이유 3줄 생성
    direction = up_reason if pct > 0 else down_reason
    if is_fx:
        context_note = "환율 변동은 수출입·물가에 영향을 줄 수 있어요."
    elif is_index:
        context_note = "지수 변동은 시장 전체 흐름을 나타내요."
    else:
        context_note = "관련 뉴스를 함께 확인해서 원인을 파악해봐요!"
    event.reason = [
        f"전일 종가 대비 {pct:+.2f}% {direction} 감지",
        f"alert_level {event.alert_level}/5 — 중요도 {event.market_impact_score} / 긴급도 {event.urgency_score}",
        context_note,
    ]

    if pct > 0:
        event.headline_mood = f"쪼아요 쪼아요 {event.ticker} {label}위로 쪼아요! {pct:+.2f}%"
    else:
        if event.alert_level == 5:
            event.headline_mood = f"으아앙 {event.ticker} {label}진짜 위험해요! 매도 고려해봐요... {pct:.2f}%"
        else:
            event.headline_mood = f"으아앙 {event.ticker} {label}흘러내려요! 조심해봐요 {pct:.2f}%"

    event.risk_note = "과거 데이터 기반 알림이에요. 투자는 신중하게 해요!"
    return event


def score_news_event(event: StockEvent) -> StockEvent:
    event.credibility_score = _credibility(event.source)
    # 영어+한국어 모두 검사
    combined = event.title + " " + event.summary
    event.sentiment = _sentiment_from_text(combined)

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
        event.headline_mood = f"으아앙 {event.ticker} 악재예요! 매도 고민해봐요"
    else:
        event.headline_mood = f"웅성웅성 {event.ticker} 일단 관망해봐요!"

    # 이유 3줄 생성 (규칙 기반 폴백용 — LLM 분석 시 덮어써짐)
    combined = event.title + " " + event.summary
    neg_hits = [kw for kw in _NEWS_NEGATIVE_KEYWORDS if kw in combined]
    pos_hits = [kw for kw in _NEWS_POSITIVE_KEYWORDS if kw in combined]
    if neg_hits:
        kw_line = f"악재 키워드 감지: {', '.join(neg_hits[:3])}"
    elif pos_hits:
        kw_line = f"호재 키워드 감지: {', '.join(pos_hits[:3])}"
    else:
        kw_line = "감정 키워드 미감지 — 중립 뉴스로 분류됐어요"

    _CRED_LABEL = {5: "주요 금융 언론", 4: "주요 언론", 3: "일반 언론", 2: "소형 미디어", 1: "커뮤니티/SNS"}
    cred_line = f"출처: {event.source} — {_CRED_LABEL.get(event.credibility_score, '미분류')} (신뢰도 {event.credibility_score}/5)"

    if event.sentiment == "negative":
        action_line = "악재 원인을 원문에서 직접 확인하고 대응 여부를 판단해봐요!"
    elif event.sentiment == "positive":
        action_line = "호재가 지속될지 추가 뉴스도 함께 확인해봐요!"
    else:
        action_line = "시장 반응을 지켜보며 추이를 확인해봐요!"

    event.reason = [kw_line, cred_line, action_line]
    event.risk_note = "뉴스 기반 알림이에요. 직접 확인해줘요!"
    return event


def score(event: StockEvent, pct: float = 0.0, is_index: bool = False) -> StockEvent:
    if event.event_type == "price_spike":
        return score_price_event(event, pct, is_index=is_index)
    return score_news_event(event)
