# -*- coding: utf-8 -*-
import logging

import discord
from discord import app_commands

import config
from db import store
from scheduler import StockPickyScheduler

logger = logging.getLogger(__name__)


class StockPickyBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.scheduler: StockPickyScheduler | None = None

    async def setup_hook(self):
        store.init_db(config.DB_PATH)
        self.scheduler = StockPickyScheduler(self)

        if config.DISCORD_GUILD_ID:
            guild = discord.Object(id=config.DISCORD_GUILD_ID)
            self.tree.copy_global_to(guild=guild)
            await self.tree.sync(guild=guild)
            logger.info("슬래시 커맨드 동기화 완료 (guild=%d)", config.DISCORD_GUILD_ID)
        else:
            await self.tree.sync()
            logger.info("슬래시 커맨드 전역 동기화 완료 (최대 1시간 소요)")

        self.scheduler.start()

    async def on_ready(self):
        logger.info("스톡피키 봇 시작! (%s)", self.user)


bot = StockPickyBot()


# ── /add ─────────────────────────────────────────────────────────────────────

@bot.tree.command(name="add", description="관심 종목을 추가해요!")
@app_commands.describe(ticker="종목 코드 (예: NVDA, 005930)", market="시장 (US 또는 KR, 기본값: US)")
async def cmd_add(
    interaction: discord.Interaction,
    ticker: str,
    market: str = "US",
):
    await interaction.response.defer(ephemeral=True)
    try:
        market = market.upper()
        if market not in ("US", "KR"):
            await interaction.followup.send("시장은 US 또는 KR만 돼요!", ephemeral=True)
            return

        success = store.add_ticker(ticker.upper(), market)
        if success:
            msg = f"쪼아요! **{ticker.upper()}** 추가됐어요! 이제 스톡피키가 열심히 볼게요!"
        else:
            msg = f"스톡피키 이미 보고 있어요! **{ticker.upper()}** 이미 목록에 있단 말이에요!"
        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        logger.warning("/add 오류: %s", e)
        await interaction.followup.send("으아앙... 오류가 났어요. 나중에 다시 해줘요!", ephemeral=True)


# ── /remove ───────────────────────────────────────────────────────────────────

@bot.tree.command(name="remove", description="관심 종목을 삭제해요.")
@app_commands.describe(ticker="종목 코드")
async def cmd_remove(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer(ephemeral=True)
    try:
        success = store.remove_ticker(ticker.upper())
        if success:
            msg = f"으아... **{ticker.upper()}** 뺐어요. 스톡피키 아쉽단 말이에요..."
        else:
            msg = f"**{ticker.upper()}** 목록에 없어요!"
        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        logger.warning("/remove 오류: %s", e)
        await interaction.followup.send("으아앙... 오류가 났어요!", ephemeral=True)


# ── /pause ────────────────────────────────────────────────────────────────────

@bot.tree.command(name="pause", description="종목 알림을 일시중단해요.")
@app_commands.describe(ticker="종목 코드")
async def cmd_pause(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer(ephemeral=True)
    try:
        success = store.pause_ticker(ticker.upper())
        if success:
            msg = f"**{ticker.upper()}** 잠깐 쉬게 할게요. 보고 싶으면 /resume 해요!"
        else:
            msg = f"**{ticker.upper()}** 목록에 없거나 이미 일시중단 상태예요!"
        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        logger.warning("/pause 오류: %s", e)
        await interaction.followup.send("으아앙... 오류가 났어요!", ephemeral=True)


# ── /resume ───────────────────────────────────────────────────────────────────

@bot.tree.command(name="resume", description="일시중단한 종목 알림을 재개해요.")
@app_commands.describe(ticker="종목 코드")
async def cmd_resume(interaction: discord.Interaction, ticker: str):
    await interaction.response.defer(ephemeral=True)
    try:
        success = store.resume_ticker(ticker.upper())
        if success:
            msg = f"쪼아요! **{ticker.upper()}** 다시 볼게요!"
        else:
            msg = f"**{ticker.upper()}** 목록에 없거나 이미 활성 상태예요!"
        await interaction.followup.send(msg, ephemeral=True)
    except Exception as e:
        logger.warning("/resume 오류: %s", e)
        await interaction.followup.send("으아앙... 오류가 났어요!", ephemeral=True)


# ── /list ─────────────────────────────────────────────────────────────────────

@bot.tree.command(name="list", description="관심 종목 목록을 보여줘요!")
async def cmd_list(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        tickers = store.get_all_tickers()

        embed = discord.Embed(
            title="스톡피키 지금 이 종목들 보고 있어요!",
            color=0x6c5ce7,
        )

        if not tickers:
            embed.description = "/add 커맨드로 종목을 추가해줘요!"
        else:
            active = [t for t in tickers if t["is_active"] == 1]
            paused = [t for t in tickers if t["is_active"] == 0]

            if active:
                lines = "\n".join(
                    f"🟢 **{t['ticker']}** ({t.get('market', 'US')})" for t in active
                )
                embed.add_field(name=f"감시 중 ({len(active)})", value=lines, inline=False)

            if paused:
                lines = "\n".join(
                    f"⏸️ **{t['ticker']}** ({t.get('market', 'US')})" for t in paused
                )
                embed.add_field(name=f"일시중단 ({len(paused)})", value=lines, inline=False)

        embed.set_footer(text=f"스톡피키 | 총 {len(tickers)}개 종목")
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logger.warning("/list 오류: %s", e)
        await interaction.followup.send("으아앙... 목록을 불러오지 못했어요!", ephemeral=True)
