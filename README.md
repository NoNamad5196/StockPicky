# 주식피키 (StockPicky)

관심 종목의 주가와 뉴스를 감시하고, 중요도·긴급도를 채점해 Discord로 실시간 알림을 보내는 주식 속보봇.  
귀여운 유령 마스코트 **주식피키** 말투로 알려줘요!

---

## 주요 기능

- **실시간 주가 감시** — 5분마다 watchlist 종목의 등락률을 체크해 급등락 시 즉시 알림
- **뉴스 수집 및 분석** — Google News RSS로 종목별 최신 뉴스 수집, Gemini LLM으로 감성 분석
- **중요도 채점** — market_impact / urgency / credibility 각 1~5점, alert_level로 통합 판단
- **하루 정리글** — 매일 16:30 KST에 오늘의 주요 이벤트 요약 브리핑 자동 발송
- **Discord 슬래시 커맨드** — 봇 재시작 없이 watchlist 실시간 관리
- **미장 + 국장 동시 지원** — US(yfinance 직접), KR(KOSPI `.KS` / KOSDAQ `.KQ` 자동 감지, 코스피·코스닥 지수 `^KS11` / `^KQ11`)

---

## 슬래시 커맨드

| 커맨드 | 설명 |
|--------|------|
| `/add [ticker]` | 관심 종목 추가 — market/name 생략 가능, 자동 감지 |
| `/remove [ticker]` | 관심 종목 삭제 |
| `/pause [ticker]` | 알림 일시중단 (DB 보존) |
| `/resume [ticker]` | 일시중단 해제 |
| `/list` | watchlist 전체 조회 (active + paused) |

모든 응답은 본인에게만 보여요 (ephemeral).

**추가 예시**
```
/add NVDA                      # 미장 자동 감지
/add 005930                    # KR 자동 감지 + 회사명 자동 조회
/add ^KS11                     # KR 지수 자동 감지
/add 005930 KR 삼성전자         # 한글 이름 직접 입력 → 뉴스 정확도↑
```

> 6자리 숫자 티커는 KR로 자동 감지해요. 회사명은 yfinance에서 자동으로 가져오지만 한국어 뉴스 검색 정확도를 높이려면 한글 이름을 직접 입력하는 걸 추천해요.

---

## 설치 및 실행

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 환경변수 설정
cp .env.example .env
# .env 파일에서 토큰/키 입력

# 3. 테스트 모드 (외부 API 없이 전체 파이프라인 검증)
python main.py

# 4. 실제 운영
python main.py --live
```

---

## 환경변수

| 변수 | 필수 | 설명 |
|------|------|------|
| `DISCORD_BOT_TOKEN` | ✅ | Discord Bot Token |
| `DISCORD_ALERT_CHANNEL_ID` | ✅ | 실시간 알림 채널 ID |
| `DISCORD_BRIEFING_CHANNEL_ID` | ✅ | 하루 정리글 채널 ID |
| `DISCORD_GUILD_ID` | | 개발 시 slash command 즉시 동기화 |
| `GEMINI_API_KEY` | | Gemini LLM 뉴스 분석 (없으면 규칙 기반 폴백) |
| `GEMINI_MODEL` | | Gemini 모델명 (기본: gemini-2.0-flash-lite) |
| `PRICE_THRESHOLD` | | 급등락 임계값 % (기본 3.0) |
| `COLLECT_INTERVAL` | | 수집 주기 초 (기본 300) |
| `BRIEFING_HOUR` | | 정리글 발송 시각 KST (기본 16) |
| `BRIEFING_MINUTE` | | 정리글 발송 분 (기본 30) |

---

## 파일 구조

```
stockpicky/
├── config.py          — 환경변수 로드 및 검증
├── models.py          — StockEvent 데이터클래스
├── scorer.py          — 중요도/긴급도/신뢰도 채점, alert_level 결정
├── formatter.py       — 주식피키 말투 Discord embed 생성
├── emojis.py          — 커스텀 이모지 캐시 및 폴백
├── llm.py             — Gemini 뉴스 분석 (google-genai SDK)
├── bot.py             — Discord Bot + 슬래시 커맨드
├── scheduler.py       — 5분 수집루프 + 16:30 KST 브리핑
├── main.py            — 진입점 (--test / --live)
├── collectors/
│   ├── price.py       — yfinance 주가 수집
│   └── news.py        — Google News RSS 뉴스 수집
├── db/
│   └── store.py       — SQLite CRUD (WAL 모드)
├── prompts/
│   └── stockpicky.py  — 주식피키 시스템 프롬프트
└── deploy/
    └── stockpicky.service  — systemd 서비스 파일
```

---

## 서버 배포 (Oracle Cloud / Ubuntu)

```bash
# 클론 후 최초 설정
git clone <repo-url> ~/stockpicky
cd ~/stockpicky
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env

# systemd 등록
sudo cp deploy/stockpicky.service /etc/systemd/system/
sudo systemctl enable stockpicky
sudo systemctl start stockpicky

# 업데이트
cd ~/stockpicky && git pull
.venv/bin/pip install -r requirements.txt
sudo systemctl restart stockpicky
sudo journalctl -u stockpicky -f
```

---

> ⚠️ 주식피키가 쪼아요라고 했지 매수하라는 뜻은 아니에요!
