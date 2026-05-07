# -*- coding: utf-8 -*-
"""
Gemini 기반 뉴스 분석 모듈 (google-genai SDK).

- analyze_news(): 뉴스 텍스트 → 구조화된 분석 결과 (JSON)
- enrich_with_llm(): StockEvent에 LLM 결과 적용 (실패 시 기존 규칙 기반 유지)
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
_semaphore: Optional[asyncio.Semaphore] = None
_MAX_CONCURRENT = 5


def _get_client() -> Optional[genai.Client]:
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            return None
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
        logger.info("Gemini 클라이언트 초기화: %s", config.GEMINI_MODEL)
    return _client


def _get_semaphore() -> asyncio.Semaphore:
    global _semaphore
    if _semaphore is None:
        _semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    return _semaphore


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

    async with _get_semaphore():
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
            logger.warning("LLM 호출 실패 (%s): %s", ticker, e)
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
    if not config.GEMINI_API_KEY:
        return events
    results = await asyncio.gather(*[enrich_with_llm(e) for e in events])
    return list(results)
