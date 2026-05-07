# -*- coding: utf-8 -*-
import argparse
import asyncio
import io
import logging
import sys

# Windows 콘솔의 cp949 문제: stdout을 UTF-8로 재설정
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("stockpicky")


# ── 테스트 모드 ───────────────────────────────────────────────────────────────

def run_test_mode():
    logger.info("=== 주식피키 테스트 모드 시작! ===")

    import config
    config.validate(mode="test")

    from db import store
    store.init_db(":memory:")

    # watchlist 테스트
    assert store.add_ticker("NVDA") is True,  "NVDA 추가 실패"
    assert store.add_ticker("NVDA") is False, "NVDA 중복 추가가 True를 반환했어요"
    assert store.add_ticker("TSLA") is True,  "TSLA 추가 실패"
    assert store.add_ticker("AAPL") is True,  "AAPL 추가 실패"
    store.pause_ticker("AAPL")

    active = store.get_active_tickers()
    assert len(active) == 2, f"active 종목이 2개여야 해요, got {len(active)}"
    assert all(t["ticker"] in ("NVDA", "TSLA") for t in active)
    logger.info("watchlist CRUD 테스트 통과!")

    # 더미 이벤트 생성
    from models import StockEvent
    from scorer import score_price_event, score_news_event
    from formatter import format_alert, format_daily_briefing

    # NVDA +4.2% 급등 → Level 5
    nvda_event = StockEvent(
        ticker="NVDA",
        event_type="price_spike",
        title="NVDA +4.20% 변동",
        summary="NVDA 현재가 950.00, 전일 대비 +4.20%",
        source="yfinance",
    )
    nvda_event = score_price_event(nvda_event, 4.2)
    assert nvda_event.alert_level == 5,   f"NVDA alert_level=5이어야 해요, got {nvda_event.alert_level}"
    assert nvda_event.should_alert is True
    assert nvda_event.sentiment == "positive"
    logger.info("NVDA Level 5 채점 통과!")

    # TSLA 악재 뉴스 → Level 4
    tsla_event = StockEvent(
        ticker="TSLA",
        event_type="news",
        title="Tesla faces major recall investigation by NHTSA",
        summary="Tesla faces major recall investigation by NHTSA due to software defects.",
        source="reuters.com",
    )
    tsla_event = score_news_event(tsla_event)
    assert tsla_event.alert_level >= 4, f"TSLA alert_level>=4이어야 해요, got {tsla_event.alert_level}"
    assert tsla_event.sentiment == "negative"
    logger.info("TSLA Level %d 채점 통과!", tsla_event.alert_level)

    # DB 저장 + 중복 방지
    nvda_id = store.save_event(nvda_event)
    assert nvda_id is not None, "NVDA 저장 실패"
    nvda_id_dup = store.save_event(nvda_event)
    assert nvda_id_dup is None, "NVDA 중복 저장이 None을 반환하지 않았어요"
    tsla_id = store.save_event(tsla_event)
    assert tsla_id is not None, "TSLA 저장 실패"
    logger.info("DB 저장 + 중복 방지 테스트 통과!")

    # 포맷터 테스트
    nvda_embed = format_alert(nvda_event)
    assert "title" in nvda_embed
    assert "description" in nvda_embed
    assert "color" in nvda_embed
    assert "쪼아요" in nvda_embed["title"] or "쪼아요" in nvda_embed["description"]
    logger.info("NVDA embed 포맷 통과!")

    tsla_embed = format_alert(tsla_event)
    assert "으아앙" in tsla_embed["title"] or "으아앙" in tsla_embed["description"]
    logger.info("TSLA embed 포맷 통과!")

    # 하루 정리글 강제 생성
    store.mark_sent(nvda_id, nvda_embed["title"])
    store.mark_sent(tsla_id, tsla_embed["title"])

    today_events = store.get_today_events(min_level=3)
    briefing = format_daily_briefing(today_events)
    assert "title" in briefing
    assert "description" in briefing
    logger.info("하루 정리글 생성 통과! (%d건)", len(today_events))

    logger.info("=== 모든 테스트 통과! 주식피키 쪼아요! ===")
    logger.info("")
    logger.info("[NVDA embed]")
    logger.info("  title: %s", nvda_embed["title"])
    logger.info("  description:\n%s", nvda_embed["description"])
    logger.info("")
    logger.info("[TSLA embed]")
    logger.info("  title: %s", tsla_embed["title"])
    logger.info("")
    logger.info("[Daily Briefing]")
    logger.info("  title: %s", briefing["title"])


# ── 실제 운영 모드 ────────────────────────────────────────────────────────────

async def run_live_mode():
    import config
    config.validate(mode="live")

    from bot import bot
    logger.info("주식피키 봇 시작! Discord에 연결 중...")
    await bot.start(config.DISCORD_BOT_TOKEN)


# ── 진입점 ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="StockPicky Bot")
    parser.add_argument(
        "--live",
        action="store_true",
        help="실제 Discord 봇 + 스케줄러 실행",
    )
    args = parser.parse_args()

    if args.live:
        asyncio.run(run_live_mode())
    else:
        run_test_mode()


if __name__ == "__main__":
    main()
