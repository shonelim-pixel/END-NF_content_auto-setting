# 📖 END NF 콘텐츠 시스템 운영 매뉴얼

## 일일 운영 워크플로우

### 자동 실행 (기본)

매일 아침 6시(KST) GitHub Actions가 자동 실행됩니다.

```
06:00  시스템 자동 실행
06:02  데이터 수집 완료
06:03  Claude API 글 생성
06:05  텔레그램으로 초안 수신
       ↓
수현님  초안 검토 → 수정 → 네이버 카페 게시
```

### 텔레그램으로 받는 내용

1. 글 초안 전문 ("END NF 션입니다"로 시작)
2. 이미지 프롬프트 (영문, 복사 가능)
3. 다음 단계 안내

### 카페 게시 절차

1. 텔레그램에서 글 초안 확인
2. 필요 시 수정 (톤, 정보 보완, 오류 수정)
3. 이미지 프롬프트를 나노바나나 또는 그록에 붙여넣기 → 이미지 생성
4. 네이버 카페에 글 + 이미지 게시

---

## 수동 실행

### GitHub에서 수동 실행

1. GitHub 저장소 → Actions 탭
2. "END NF Daily Content Pipeline" 클릭
3. "Run workflow" 버튼
4. 요일 입력 (예: `thu`) → 실행

### 로컬에서 실행

```bash
# 특정 요일 전체 파이프라인
python simulate_pipeline.py --day mon --live

# 수집만
python daily_runner.py --day mon

# 글 생성만 (이미 수집된 데이터 기반)
python content_generator.py --day mon

# 이미지 프롬프트만
python image_prompt_generator.py --day mon --both

# 알림만 (이미 생성된 글 기반)
python notification_sender.py --day mon
```

---

## 이미지 생성 가이드

### 나노바나나 사용법

1. https://nanobana.na 접속
2. `output/image_prompts_{요일}_{날짜}.txt` 파일의 프롬프트 복사
3. 붙여넣기 → 생성
4. 비율: 1:1 (정사각형) 또는 3:4 (카드뉴스)

### 그록 사용법

1. Grok 이미지 생성 도구 접속
2. 같은 `.txt` 파일의 프롬프트 복사
3. 영문 프롬프트 그대로 사용

### 네거티브 프롬프트

`.txt` 파일 하단의 네거티브 프롬프트도 함께 입력하면 어두운/부적절한 이미지를 방지합니다.

### 카드뉴스 만들기

```bash
# 3장 카드뉴스
python image_prompt_generator.py --day thu --style card_3

# 5장 카드뉴스
python image_prompt_generator.py --day thu --style card_5
```

각 슬라이드별로 역할이 다릅니다:
- 표지: 시선을 끄는 메인 비주얼
- 본문: 핵심 정보 시각화
- 마무리: 따뜻한 응원 + CTA

---

## 트러블슈팅

### 텔레그램 메시지가 안 올 때

1. GitHub → Actions 탭에서 실행 로그 확인
2. Secrets에 `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID` 확인
3. 로컬에서 테스트: `python notification_sender.py --test`

### 수집 데이터가 0건일 때

- PubMed/ClinicalTrials.gov API 일시 장애일 수 있음
- 다음 날 자동 재실행됨
- 수동 실행: GitHub Actions에서 "Run workflow"

### Claude API 글 생성 실패

- `ANTHROPIC_API_KEY` 확인
- API 크레딧 잔액 확인
- 미리보기 모드로 동작 (수집 데이터는 정상 저장)

### GitHub Actions가 실행 안 될 때

- 저장소가 60일 이상 비활성이면 cron이 비활성화될 수 있음
- 해결: 아무 커밋 push 또는 수동 실행

---

## 비용 안내

| 항목 | 예상 비용 |
|------|----------|
| GitHub Actions | 무료 (public repo) 또는 월 2,000분 무료 (private) |
| Claude API | 하루 약 $0.01~0.03 (Sonnet 기준) |
| 텔레그램 | 무료 |
| PubMed API | 무료 |

월 예상 비용: $0.30~$1.00

---

## 커스터마이징

### 새로운 소스 추가

`source_config.yaml`에 소스 추가 후, `news_fetcher.py`에 스크래핑 로직 추가

### 프롬프트 수정

`content_generator.py`의 `DAY_PROMPTS` 딕셔너리에서 각 요일별 시스템/유저 프롬프트 수정

### 이미지 스타일 변경

`image_prompt_generator.py`의 `DAY_VISUAL_STYLES`에서 요일별 테마/색감/요소 수정

### 전송 시간 변경

`.github/workflows/daily_collect.yml`의 cron 표현식 수정:
```yaml
# 현재: UTC 21:00 = KST 06:00
- cron: '0 21 * * *'

# 예: KST 08:00으로 변경
- cron: '0 23 * * *'
```
