# -*- coding: utf-8 -*-
"""
서버 커스텀 이모지 캐시.

봇 on_ready 시 populate()를 호출하면 이후 get()으로 어디서든 사용 가능.
이모지가 없으면 fallback 텍스트를 반환하므로 --test 모드에서도 안전.

등록된 이모지:
  :jjowayo:   → 호재/급등/긍정 상황
  :uaaang:    → 악재/급락/부정 상황
  :ggang:     → 강한 충격/대형 이벤트 강조
  :yolsimhi:  → 열심히 모니터링 중 / 일상 수집 / 브리핑 헤더
"""

_cache: dict[str, str] = {}


def populate(guild_emojis) -> None:
    _cache.clear()
    for emoji in guild_emojis:
        _cache[emoji.name] = str(emoji)


def get(name: str, fallback: str = "") -> str:
    return _cache.get(name, fallback)


# 편의 함수 — formatter.py가 직접 호출
def jjowayo(repeat: int = 1) -> str:
    e = get("jjowayo", "쪼아요")
    return " ".join([e] * repeat)


def uaaang(repeat: int = 1) -> str:
    e = get("uaaang", "으아앙")
    return " ".join([e] * repeat)


def ggang() -> str:
    return get("ggang", "💥")


def yolsimhi() -> str:
    return get("yolsimhi", "🔍")
