# StockPicky Bot — 프로젝트 컨텍스트

## 개요
관심 종목의 주가·거래량·뉴스를 감시하고, 중요도/긴급도를 채점한 뒤, 스톡피키(귀여운 유령 마스코트) 말투로 Discord에 실시간 알림과 하루 요약 브리핑을 전달하는 주식 속보봇.

## 파일 구조
```
stockpicky/
├── config.py          — 환경변수 로드 및 검증 (python-dotenv)
├── models.py          — StockEvent 데이터클래스
├── scorer.py          — 순수 함수: 중요도/긴급도/신뢰도 채점, alert_level 결정
├── formatter.py       — 규칙 기반 스톡피키 말투 Discord embed dict 생성
├── bot.py             — Discord Bot + /add /remove /pause /list 슬래시 커맨드
├── scheduler.py       — discord.ext.tasks 기반 5분 수집루프 + 16:30 KST 브리핑
├── main.py            — 진입점: --test(기본) / --live 모드
├── collectors/
│   ├── price.py       — yfinance 주가/등락률 수집 → StockEvent
│   └── news.py        — Google News RSS + feedparser 뉴스 수집 → StockEvent
├── db/
│   └── store.py       — SQLite CRUD (WAL 모드, 중복 방지, watchlist 관리)
└── prompts/
    └── stockpicky.py  — 스톡피키 시스템 프롬프트 상수
```

## 실행 방법
```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일에서 DISCORD_BOT_TOKEN 등 입력

# 테스트 모드 (외부 API 없이 전체 파이프라인 검증)
python main.py --test

# 실제 운영
python main.py --live
```

## 환경변수
| 변수 | 설명 |
|------|------|
| `DISCORD_BOT_TOKEN` | Discord Bot Token |
| `DISCORD_ALERT_CHANNEL_ID` | 실시간 알림 채널 ID |
| `DISCORD_BRIEFING_CHANNEL_ID` | 하루 정리글 채널 ID |
| `DISCORD_GUILD_ID` | (선택) 개발 시 빠른 slash command sync |
| `PRICE_THRESHOLD` | 급등락 임계값 % (기본 3.0) |
| `COLLECT_INTERVAL` | 수집 주기 초 (기본 300) |
| `BRIEFING_HOUR` | 정리글 발송 시각 KST (기본 16) |
| `BRIEFING_MINUTE` | 정리글 발송 분 (기본 30) |

## Slash Command
| 커맨드 | 설명 |
|--------|------|
| `/add [ticker] [market=US]` | 관심 종목 추가 |
| `/remove [ticker]` | 관심 종목 삭제 |
| `/pause [ticker]` | 알림 일시중단 (DB 보존) |
| `/list` | 현재 watchlist 조회 (active + paused) |

응답은 모두 ephemeral=True (본인에게만 보임).

## Watchlist 관리 방식
- 종목은 SQLite `watchlist` 테이블에 저장
- 수집 루프(5분마다)가 `get_active_tickers()`를 **매번 새로 호출** (캐싱 금지)
- `/add`로 추가하면 다음 수집 사이클부터 자동 반영 (봇 재시작 불필요)

## 주의사항
- `print()` 사용 금지 → `logging` 모듈만 사용
- `get_active_tickers()`는 절대 캐싱하지 않을 것
- 모든 파일 UTF-8 인코딩
- DB 파일명: `stockpicky.db`
- 외부 API 호출은 반드시 try/except 후 logging.warning
