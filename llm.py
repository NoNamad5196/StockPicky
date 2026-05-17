# -*- coding: utf-8 -*-
"""
Gemini 기반 뉴스 분석 모듈 (google-genai SDK).

- analyze_news(): 뉴스 텍스트 → 구조화된 분석 결과 (JSON)
- enrich_with_llm(): StockEvent에 LLM 결과 적용 (실패 시 기존 규칙 기반 유지)

Rate limit 대응:
  - 요청을 순차 처리 (동시 1개)하여 burst 방지
  - 요청 사이 _REQ_INTERVAL 초 강제 대기 (15 RPM = 4초/req)
  - 429 수신 시 exponential backoff 재시도 (최대 2회)
"""
import asyncio
import json
import logging
from typing import Optional

from google import genai
from google.genai import types

import config
from models import StockEvent
from prompts.stockpicky import NEWS_ANALYSIS_PROMPT

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None

# 15 RPM(무료 기본 한도) 기준: 요청 1개당 최소 4초 간격
_REQ_INTERVAL  = 4.0        # 요청 간 최소 대기 (초)
_RETRY_DELAYS  = [10, 30]   # 429 발생 시 재시도 전 대기 시간 (초)


def _get_client() -> Optional[genai.Client]:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            return None
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
        logger.info("Gemini 클라이언트 초기화: %s", config.GEMINI_MODEL)
    return _client


def _is_rate_limit_error(e: Exception) -> bool:
    """429 / quota 초과 에러 여부 판별."""
    msg = str(e).lower()
    return "429" in msg or "quota" in msg or "resource_exhausted" in msg or "rate_limit" in msg


async def analyze_news(
    ticker: str,
    title: str,
    summary: str,
    source: str,
) -> Optional[dict]:
    client = _get_client()
    if client is None:
        return None

    prompt = NEWS_ANALYSIS_PROMPT.format(
        ticker=ticker,
        title=title,
        summary=summary[:800],
        source=source,
    )

    for attempt in range(len(_RETRY_DELAYS) + 1):
        try:
            response = await client.aio.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            result = json.loads(response.text)

            required = {"sentiment", "market_impact_score", "urgency_score",
                        "credibility_score", "headline_mood", "summary"}
            if not required.issubset(result.keys()):
                logger.warning("LLM 응답 필드 누락 (%s): %s", ticker, list(result.keys()))
                return None

            for key in ("market_impact_score", "urgency_score", "credibility_score"):
                result[key] = max(1, min(5, int(result.get(key, 1))))

            return result

        except json.JSONDecodeError as e:
            logger.warning("LLM JSON 파싱 실패 (%s): %s", ticker, e)
            return None

        except Exception as e:
            if _is_rate_limit_error(e):
                if attempt < len(_RETRY_DELAYS):
                    wait = _RETRY_DELAYS[attempt]
                    logger.warning(
                        "429 Rate limit (%s) — %d초 대기 후 재시도 (%d/%d)",
                        ticker, wait, attempt + 1, len(_RETRY_DELAYS),
                    )
                    await asyncio.sleep(wait)
                    continue
                logger.warning("429 재시도 횟수 초과 — 규칙 기반으로 폴백: %s", ticker)
            else:
                logger.warning("LLM 호출 실패 (%s): %s", ticker, e)
            return None

    return None


def _recalc_alert_level(impact: int, urgency: int) -> tuple[int, bool]:
    if impact >= 4 and urgency >= 4:
        return 5, True
    if impact >= 3 and urgency >= 3:
        return 4, True
    if impact >= 2:
        return 3, False
    return 2, False


async def enrich_with_llm(event: StockEvent) -> StockEvent:
    if event.event_type != "news":
        return event

    result = await analyze_news(event.ticker, event.title, event.summary, event.source)
    if result is None:
        logger.debug("LLM 폴백 → 규칙 기반 사용: %s", event.ticker)
        return event

    event.sentiment           = result.get("sentiment", event.sentiment)
    event.market_impact_score = result.get("market_impact_score", event.market_impact_score)
    event.urgency_score       = result.get("urgency_score", event.urgency_score)
    event.credibility_score   = result.get("credibility_score", event.credibility_score)
    event.headline_mood       = result.get("headline_mood", event.headline_mood)
    event.summary             = result.get("summary", event.summary)
    event.reason              = result.get("reason", event.reason)
    event.risk_note           = result.get("risk_note", event.risk_note)

    level, should = _recalc_alert_level(event.market_impact_score, event.urgency_score)
    event.alert_level  = level
    event.should_alert = should

    logger.debug("LLM 분석 완료: %s → Level %d (%s)", event.ticker, level, event.sentiment)
    return event


async def enrich_all(events: list[StockEvent]) -> list[StockEvent]:
    """뉴스 이벤트를 순차 처리 — burst 방지용 요청 간격 유지."""
    if not config.GEMINI_API_KEY:
        return events

    results: list[StockEvent] = []
    news_events = [e for e in events if e.event_type == "news"]
    other_events = [e for e in events if e.event_type != "news"]

    for i, event in enumerate(news_events):
        result = await enrich_with_llm(event)
        results.append(result)
        # 마지막 요청 제외하고 최소 간격 대기 (15 RPM = 4초/req)
        if i < len(news_events) - 1:
            await asyncio.sleep(_REQ_INTERVAL)

    return other_events + results
