# -*- coding: utf-8 -*-
import asyncio
import logging
from datetime import datetime, timezone, timedelta, time as dt_time

import discord
from discord.ext import tasks

import config
from db import store
from collectors.price import collect_all_prices
from collectors.news import collect_all_news
from formatter import format_alert, format_daily_briefing
from llm import enrich_all

logger = logging.getLogger(__name__)

KST = timezone(timedelta(hours=9))
_BATCH_FLUSH_CYCLES = 6   # 6 × 5min = 30min


class StockPickyScheduler:
    def __init__(self, bot: discord.Client):
        self.bot = bot
        self._level3_buffer: list = []
        self._batch_cycle_count: int = 0

        # ── 5분 수집 루프 ─────────────────────────────────────────────────────
        @tasks.loop(seconds=config.COLLECT_INTERVAL)
        async def collection_loop():
            await self._run_collection()

        @collection_loop.before_loop
        async def before_collection():
            await self.bot.wait_until_ready()
            logger.info("주식피키 수집 루프 준비 완료!")

        self.collection_loop = collection_loop

        # ── 하루 정리글 루프 ──────────────────────────────────────────────────
        briefing_time = dt_time(
            hour=config.BRIEFING_HOUR,
            minute=config.BRIEFING_MINUTE,
            tzinfo=KST,
        )

        @tasks.loop(time=briefing_time)
        async def briefing_loop():
            await self._send_daily_briefing()

        @briefing_loop.before_loop
        async def before_briefing():
            await self.bot.wait_until_ready()

        self.briefing_loop = briefing_loop

    def start(self):
        self.collection_loop.start()
        self.briefing_loop.start()
        logger.info("주식피키 스케줄러 시작!")

    def stop(self):
        self.collection_loop.cancel()
        self.briefing_loop.cancel()

    # ── 수집 루프 본체 ────────────────────────────────────────────────────────

    async def _run_collection(self):
        tickers = store.get_active_tickers()
        if not tickers:
            logger.debug("watchlist 비어있어요.")
            return

        logger.info("수집 시작 — %d개 종목", len(tickers))

        loop = asyncio.get_event_loop()
        price_events, news_events = await asyncio.gather(
            loop.run_in_executor(None, collect_all_prices, tickers),
            loop.run_in_executor(None, collect_all_news, tickers),
        )
        logger.info("수집 결과: 주가 %d건, 뉴스 %d건", len(price_events), len(news_events))

        # 뉴스 이벤트만 LLM으로 분석 (GEMINI_API_KEY 없으면 자동 스킵)
        news_events = await enrich_all(news_events)

        all_events = price_events + news_events

        for event in all_events:
            event_id = store.save_event(event)
            if event_id is None:
                continue

            if event.alert_level >= 4:
                await self._send_alert(event, event_id)
            elif event.alert_level == 3:
                self._level3_buffer.append((event, event_id))

        self._batch_cycle_count += 1
        if self._batch_cycle_count >= _BATCH_FLUSH_CYCLES and self._level3_buffer:
            await self._flush_batch()
            self._batch_cycle_count = 0

    async def _send_alert(self, event, event_id: int):
        channel = self.bot.get_channel(config.DISCORD_ALERT_CHANNEL_ID)
        if channel is None:
            logger.warning("알림 채널을 찾을 수 없어요: %d", config.DISCORD_ALERT_CHANNEL_ID)
            return
        try:
            embed_data = format_alert(event)
            embed = _build_embed(embed_data)
            await channel.send(embed=embed)
            store.mark_sent(event_id, embed_data["title"][:200])
            logger.info("알림 발송: %s (Level %d)", event.ticker, event.alert_level)
        except Exception as e:
            logger.warning("알림 발송 실패: %s", e)

    async def _flush_batch(self):
        if not self._level3_buffer:
            return
        channel = self.bot.get_channel(config.DISCORD_ALERT_CHANNEL_ID)
        if channel is None:
            logger.warning("알림 채널을 찾을 수 없어요: %d", config.DISCORD_ALERT_CHANNEL_ID)
            return

        logger.info("Level 3 묶음 발송 — %d건", len(self._level3_buffer))
        for event, event_id in self._level3_buffer:
            try:
                embed_data = format_alert(event)
                embed = _build_embed(embed_data)
                await channel.send(embed=embed)
                store.mark_sent(event_id, embed_data["title"][:200])
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.warning("묶음 발송 실패: %s", e)

        self._level3_buffer.clear()

    # ── 하루 정리글 ───────────────────────────────────────────────────────────

    async def _send_daily_briefing(self):
        channel = self.bot.get_channel(config.DISCORD_BRIEFING_CHANNEL_ID)
        if channel is None:
            logger.warning("브리핑 채널을 찾을 수 없어요: %d", config.DISCORD_BRIEFING_CHANNEL_ID)
            return

        today = datetime.now(KST).strftime("%Y-%m-%d")
        events = store.get_today_events(min_level=3)
        logger.info("하루 정리글 발송 — %d건", len(events))

        embed_data = format_daily_briefing(events)
        embed = _build_embed(embed_data)

        try:
            await channel.send(embed=embed)
            store.save_daily_report(today, "daily", embed_data["description"])
            logger.info("하루 정리글 발송 완료")
        except Exception as e:
            logger.warning("하루 정리글 발송 실패: %s", e)

    async def send_briefing_now(self):
        """테스트/강제 발송용."""
        await self._send_daily_briefing()


def _build_embed(data: dict) -> discord.Embed:
    embed = discord.Embed(
        title=data.get("title", ""),
        description=data.get("description", ""),
        color=data.get("color", 0x636e72),
    )
    embed.set_footer(text=data.get("footer", "주식피키"))
    return embed
