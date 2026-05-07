# -*- coding: utf-8 -*-
import os
import logging
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DISCORD_BOT_TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
DISCORD_ALERT_CHANNEL_ID: int = int(os.getenv("DISCORD_ALERT_CHANNEL_ID", "0"))
DISCORD_BRIEFING_CHANNEL_ID: int = int(os.getenv("DISCORD_BRIEFING_CHANNEL_ID", "0"))
DISCORD_GUILD_ID: int = int(os.getenv("DISCORD_GUILD_ID", "0"))

PRICE_THRESHOLD: float = float(os.getenv("PRICE_THRESHOLD", "3.0"))
COLLECT_INTERVAL: int = int(os.getenv("COLLECT_INTERVAL", "300"))
BRIEFING_HOUR: int = int(os.getenv("BRIEFING_HOUR", "16"))
BRIEFING_MINUTE: int = int(os.getenv("BRIEFING_MINUTE", "30"))

DB_PATH: str = os.getenv("DB_PATH", "stockpicky.db")

GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite-preview")


def validate(mode: str = "live") -> None:
    errors = []

    if mode == "live":
        if not DISCORD_BOT_TOKEN:
            errors.append("DISCORD_BOT_TOKEN이 없어요!")
        if DISCORD_ALERT_CHANNEL_ID == 0:
            errors.append("DISCORD_ALERT_CHANNEL_ID가 없어요!")
        if DISCORD_BRIEFING_CHANNEL_ID == 0:
            errors.append("DISCORD_BRIEFING_CHANNEL_ID가 없어요!")

    if errors:
        for e in errors:
            logger.error(e)
        raise EnvironmentError("환경변수 설정을 확인해줘요!\n" + "\n".join(errors))

    logger.info("설정 검증 완료 (mode=%s)", mode)
