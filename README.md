# 🧬 END NF 자동 콘텐츠 생산 시스템

매일 NF(신경섬유종) 관련 최신 정보를 자동 수집하고, "END NF 션입니다" 스타일의 카페 포스팅 초안을 생성하여 텔레그램으로 전송합니다.

## 시스템 흐름

```
매일 KST 06:00 (GitHub Actions)
    │
    ├─ 📦 수집 (daily_runner.py)
    │   PubMed · ClinicalTrials.gov · 레어노트 · CTF · Google News · Reddit
    │
    ├─ ✍️ 글 생성 (content_generator.py + Claude API)
    │   요일별 프롬프트 → "END NF 션입니다" 스타일
    │
    ├─ 🎨 이미지 (image_prompt_generator.py)
    │   나노바나나/그록 최적화 · 카드뉴스 레이아웃
    │
    └─ 📮 전송 (notification_sender.py)
        텔레그램 + 이메일 → 수현님 검토 → 네이버 카페 게시
```

## 요일별 콘텐츠

| 요일 | 주제 | 주요 소스 |
|------|------|----------|
| 월 | 📚 최신 논문/연구 | PubMed, 레어노트, CTF |
| 화 | 💛 환자/가족 응원 | Reddit, CTF Stories |
| 수 | 🌍 해외 커뮤니티 | CTF News, NF Network |
| 목 | 💊 치료제/임상시험 | ClinicalTrials.gov, CTF Pipeline |
| 금 | 📋 정책/복지 | 레어노트, NORD |
| 토 | 🌿 힐링 콘텐츠 | Reddit, 레어노트 |
| 일 | 📰 주간 하이라이트 | 전체 데이터 요약 |

## 빠른 시작

```bash
git clone https://github.com/YOUR_REPO/endnf-content-system.git
cd endnf-content-system
pip install -r requirements.txt

# 환경변수
export ANTHROPIC_API_KEY="your-key"
export TELEGRAM_BOT_TOKEN="your-token"
export TELEGRAM_CHAT_ID="your-id"

# E2E 시뮬레이션
python simulate_pipeline.py --day thu

# 실제 실행
python simulate_pipeline.py --day thu --live
```

## 파일 구조

```
├── daily_runner.py            # 메인 오케스트레이터
├── content_generator.py       # Claude API 글 생성
├── image_prompt_generator.py  # 이미지 프롬프트
├── notification_sender.py     # 텔레그램/이메일 전송
├── pubmed_fetcher.py          # PubMed 수집
├── news_fetcher.py            # 뉴스/RSS/스크래핑
├── clinical_trials_fetcher.py # 임상시험 수집
├── patient_story_fetcher.py   # 환자 이야기 수집
├── utils.py                   # 공통 유틸리티
├── simulate_pipeline.py       # E2E 시뮬레이션
├── test_local.py              # 로컬 테스트
├── source_config.yaml         # 소스 설정
├── TELEGRAM_SETUP.md          # 텔레그램 봇 설정 가이드
├── OPERATIONS_MANUAL.md       # 운영 매뉴얼
└── .github/workflows/
    └── daily_collect.yml      # GitHub Actions
```

## GitHub Secrets

| Secret | 필수 | 설명 |
|--------|------|------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API 키 |
| `TELEGRAM_BOT_TOKEN` | ✅ | 텔레그램 봇 토큰 |
| `TELEGRAM_CHAT_ID` | ✅ | 수신 채팅 ID |
| `NCBI_API_KEY` | | PubMed API (없어도 동작) |
| `SMTP_USER` / `SMTP_PASS` | | 이메일 알림 (선택) |

## 주요 명령어

```bash
python daily_runner.py --day mon                    # 수집
python content_generator.py --day mon --preview     # 글 미리보기
python image_prompt_generator.py --day mon --both   # 이미지 프롬프트
python notification_sender.py --test                # 텔레그램 테스트
python test_local.py --module all                   # 전체 테스트
```
