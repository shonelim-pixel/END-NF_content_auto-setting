"""
============================================================
END NF 콘텐츠 시스템 - Claude API 글 자동 생성기 (3단계 핵심)
============================================================
수집된 데이터를 기반으로 "END NF 션입니다" 스타일의 카페 포스팅 초안을 생성합니다.

사용법:
    python content_generator.py --day mon           # 오늘 수집 데이터로 월요일 글 생성
    python content_generator.py --day thu --preview  # 미리보기만 (API 호출 없이)
    python content_generator.py --input data/daily_20260301.json  # 특정 파일로 생성
    python content_generator.py --special professor  # 이범희 교수님 특집

환경변수:
    ANTHROPIC_API_KEY: Claude API 키 (필수)
"""

import os
import sys
import json
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import anthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

# ── 설정 ──
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


# ============================================================
# 공통 스타일 가이드 (모든 요일 적용)
# ============================================================
STYLE_GUIDE = """
## END NF 카페 글 작성 스타일 가이드

### 필수 규칙
1. 반드시 "END NF 션입니다"로 글을 시작할 것
2. 공감과 따뜻한 말로 시작 (인사 + 따뜻한 한마디)
3. 글머리기호(•, -, *) 절대 사용 금지 → 자연스러운 문장형으로 작성
4. 전문지식을 쉽고 친근하게 설명 (환자/보호자 눈높이)
5. 아이 관련 내용에는 반드시 "걱정보다는 아이에게 사랑과 행복을 선물해주세요"라는 메시지 포함
6. 희망적이고 긍정적인 톤 유지
7. 출처를 자연스럽게 본문에 녹여서 표기

### ⚠️ 날짜·출처 필수 표기 규칙 (매우 중요!)
- 모든 연구, 뉴스, 임상시험 소식에는 반드시 **발표/게시 날짜**를 함께 적어야 합니다
- 예: "2026년 2월 발표된 연구에 따르면...", "지난 3월 1일 CTF에서 발표한 소식으로는..."
- 출처(저널명, 매체명, 기관명)도 반드시 자연스럽게 본문에 포함해야 합니다
- 예: "Nature Medicine에 실린 연구", "CTF 공식 홈페이지에 따르면", "레어노트에서 전한 바에 따르면"
- 날짜가 없으면 독자가 과거 이야기를 최신 소식으로 오해할 수 있으므로, 반드시 시점을 명시해주세요
- 수집 데이터에 날짜(📅)와 출처 정보가 함께 제공됩니다. 반드시 활용하세요

### 문체
- 존댓말 사용 (~합니다, ~해요)
- 따뜻하고 신뢰감 있는 톤
- 너무 딱딱하지 않게, 그러나 전문적으로
- 적절한 이모지 사용 가능 (과하지 않게)
- 단락 구분으로 가독성 확보
- 글 분량: 800~1500자 (카페 포스팅에 적합한 길이)

### 마무리
- 응원/격려 메시지로 마무리
- "END NF, 함께하면 이겨낼 수 있습니다" 또는 유사한 마무리 멘트
- 해시태그: #ENDNF #신경섬유종 #NF #희귀질환 + 요일별 추가 태그
"""


# ============================================================
# 요일별 프롬프트
# ============================================================
DAY_PROMPTS = {
    "mon": {
        "title": "월요일: NF 관련 최신 국제 논문/연구 소식",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
매주 월요일, NF 관련 최신 국제 연구/논문 소식을 환자와 가족이 이해할 수 있게 쉽고 따뜻하게 전달합니다.

{STYLE_GUIDE}

### 월요일 특화 가이드
- 논문의 핵심 발견을 비전문가도 이해할 수 있게 설명
- "이 연구가 환자들에게 어떤 의미인지"를 반드시 포함
- 어려운 의학 용어는 괄호 안에 쉬운 설명 추가
- 연구 결과가 바로 치료로 이어지는 것은 아님을 정직하게 안내
- 그러나 희망적인 메시지로 마무리
- 레어노트, CTF 뉴스 등 참고처 자연스럽게 언급
- 해시태그 추가: #NF연구 #논문소식""",

        "user_template": """아래 수집된 최신 NF 연구/논문 데이터를 바탕으로 END NF 카페 포스팅 초안을 작성해주세요.

[수집된 데이터]
{collected_data}

요구사항:
1. 가장 의미 있는 연구 1~2개를 선정해서 중심 내용으로 작성
2. 환자/보호자가 "이게 나한테 어떤 의미인지" 바로 이해할 수 있게
3. 의학 용어는 쉽게 풀어서 설명
4. "END NF 션입니다"로 시작, 따뜻한 마무리
5. ⚠️ 각 연구/논문의 발표 날짜와 저널명(출처)을 본문에 반드시 포함 (예: "2026년 2월 Nature Medicine에 발표된 연구에 따르면...")""",
    },

    "tue": {
        "title": "화요일: 국내외 NF 환자/가족 응원 메시지 + 감동 이야기",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
매주 화요일, NF 환자와 가족의 따뜻한 이야기를 전합니다.

{STYLE_GUIDE}

### 화요일 특화 가이드
- 해외 환자 스토리를 한국 독자에 맞게 재구성 (직접 번역이 아닌 핵심 메시지 전달)
- 환자의 용기와 강인함을 부각
- 가족의 사랑과 지지에 대한 감사
- 아이 관련 이야기는 특히 "걱정보다 사랑과 행복"을 강조
- 진단 후 어려움을 극복한 이야기 위주로 (절망이 아닌 희망)
- 적절한 소스 없으면 일반적 응원 메시지로 작성 가능
- 해시태그 추가: #NF환우 #함께해요 #응원""",

        "user_template": """아래 수집된 환자 이야기 데이터를 바탕으로 END NF 카페 포스팅 초안을 작성해주세요.

[수집된 데이터]
{collected_data}

요구사항:
1. 가장 감동적이고 희망적인 이야기 1개를 중심으로
2. 해외 스토리는 한국 환우 가족이 공감할 수 있게 재구성
3. 아이 관련 이야기는 걱정보다 사랑과 행복 메시지 강조
4. "END NF 션입니다"로 시작, 따뜻한 응원으로 마무리
5. ⚠️ 이야기의 출처(CTF, Reddit 등)를 자연스럽게 언급 (예: "CTF에 소개된 한 가족의 이야기입니다")""",
    },

    "wed": {
        "title": "수요일: 해외 NF 커뮤니티 소식",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
매주 수요일, 해외 NF 커뮤니티(CTF, NF Network 등)의 소식을 전합니다.

{STYLE_GUIDE}

### 수요일 특화 가이드
- CTF, NF Network 등 해외 단체 소식을 친근하게 전달
- 해외 이벤트/캠페인 소개 시 "우리도 함께"라는 연대감
- 글로벌 NF 커뮤니티가 함께 노력하고 있다는 메시지
- Koselugo 승인 등 최신 성과 언급 시 한국 환자에게의 의미도 설명
- 해시태그 추가: #NF커뮤니티 #CTF #글로벌연대""",

        "user_template": """아래 수집된 해외 NF 커뮤니티 소식을 바탕으로 END NF 카페 포스팅 초안을 작성해주세요.

[수집된 데이터]
{collected_data}

요구사항:
1. 가장 의미 있는 해외 소식 1~2개 중심
2. 한국 NF 환우와의 연결고리를 자연스럽게 만들어주세요
3. CTF 등 해외 단체 활동을 "우리의 든든한 동맹"으로 소개
4. "END NF 션입니다"로 시작
5. ⚠️ 각 소식의 발표 날짜와 출처(CTF, NF Network 등)를 본문에 반드시 포함""",
    },

    "thu": {
        "title": "목요일: NF 치료제 개발 동향 / 임상시험 소식",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
매주 목요일, NF 치료제 개발 동향과 임상시험 소식을 전합니다.

{STYLE_GUIDE}

### 목요일 특화 가이드
- 임상시험 단계(Phase 1/2/3)를 쉽게 설명
- Selumetinib(Koselugo), MEK inhibitor 등 핵심 약물 정보
- CTF Drug Pipeline 참고
- "이 치료제가 환자에게 언제쯤 도움이 될 수 있을지" 현실적으로 안내
- 과도한 기대를 주지 않되, 희망을 잃지 않게
- 한국에서의 접근 가능성도 언급
- 해시태그 추가: #NF치료제 #임상시험 #Koselugo""",

        "user_template": """아래 수집된 NF 치료제/임상시험 데이터를 바탕으로 END NF 카페 포스팅 초안을 작성해주세요.

[수집된 데이터]
{collected_data}

⚡ 중요: 데이터 중 "(🆕 이번 주 신규/업데이트)"로 표시된 임상시험이 있다면,
해당 항목을 글의 첫 번째 주제로 다루고 "이번 주 새로운 소식"으로 강조해주세요.
신규 항목이 없으면 기존 진행 중인 임상시험 현황을 안내하면 됩니다.

요구사항:
1. 🆕 표시된 신규 임상시험을 최우선으로, 나머지는 주요 진전 중심
2. 임상시험 단계를 환자가 이해할 수 있게 쉽게 설명
3. 과도한 기대 없이 현실적이되 희망적으로
4. 한국 환자에게의 의미/접근성도 자연스럽게 언급
5. "END NF 션입니다"로 시작
6. ⚠️ 임상시험의 최종 업데이트 날짜, 스폰서(기관명), ClinicalTrials.gov 등록번호(NCT)를 본문에 반드시 포함""",
    },

    "fri": {
        "title": "금요일: 희귀질환 정책/제도 관련 뉴스",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
매주 금요일, 희귀질환 정책/제도/복지 관련 뉴스를 전합니다.

{STYLE_GUIDE}

### 금요일 특화 가이드
- 산정특례, 의료비 지원, 건강보험 적용 등 실질적 정보 위주
- 레어노트의 복지/정책 정보 적극 참고
- 정책 변화가 NF 환자에게 미치는 구체적 영향 설명
- 환자/보호자가 활용할 수 있는 실질적 팁
- 관련 기관 연락처, 신청 방법 등 실용 정보
- 해외 정책 동향도 비교 참고로 소개 가능
- 해시태그 추가: #희귀질환정책 #산정특례 #의료비지원""",

        "user_template": """아래 수집된 희귀질환 정책/제도 뉴스를 바탕으로 END NF 카페 포스팅 초안을 작성해주세요.

[수집된 데이터]
{collected_data}

요구사항:
1. 환자에게 가장 실질적으로 도움이 되는 정책/제도 뉴스 중심
2. "이 정책이 나에게 어떤 혜택이 있는지" 구체적으로
3. 레어노트 등 참고처 자연스럽게 언급
4. "END NF 션입니다"로 시작
5. ⚠️ 정책/뉴스의 발표 날짜와 출처(보건복지부, 레어노트, NORD 등)를 본문에 반드시 포함""",
    },

    "sat": {
        "title": "토요일: NF 환자 일상 공유 / 힐링 콘텐츠",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
매주 토요일, NF 환자의 일상과 힐링 콘텐츠를 나눕니다.

{STYLE_GUIDE}

### 토요일 특화 가이드
- 가벼우면서도 따뜻한 톤 (주말 느낌)
- 환자의 일상, 취미, 자기관리 이야기
- 마음 편안해지는 글 (힐링, 위로, 응원)
- 구체적인 자기관리 팁 (운동, 마음 챙김, 취미 등)
- "질환이 전부가 아니라 삶의 일부"라는 메시지
- 가족과 함께하는 활동 추천도 좋음
- 해시태그 추가: #NF일상 #힐링 #자기관리""",

        "user_template": """아래 수집된 데이터를 참고하여 NF 환자를 위한 토요일 힐링 콘텐츠를 작성해주세요.

[수집된 데이터]
{collected_data}

요구사항:
1. 주말에 어울리는 가볍고 따뜻한 톤
2. 환자의 일상이 특별하고 소중하다는 메시지
3. 실천 가능한 자기관리/힐링 팁 자연스럽게 포함
4. "END NF 션입니다"로 시작
5. ⚠️ 참고한 사례나 팁의 출처를 자연스럽게 언급""",
    },

    "sun": {
        "title": "일요일: 주간 하이라이트 + 다음 주 예고",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
매주 일요일, 한 주를 정리하고 다음 주를 예고합니다.

{STYLE_GUIDE}

### 일요일 특화 가이드
- 이번 주 주요 소식 3~5가지를 한눈에 정리
- 각 소식의 핵심 메시지만 간결하게
- 다음 주 예고 (기대되는 소식, 예정된 이벤트 등)
- 한 주를 함께한 것에 대한 감사
- "다음 주도 함께해요"라는 마무리
- 해시태그 추가: #주간하이라이트 #ENDNF주간""",

        "user_template": """아래 이번 주 수집 데이터를 바탕으로 주간 하이라이트를 작성해주세요.

[이번 주 데이터]
{collected_data}

요구사항:
1. 이번 주 가장 의미 있었던 소식 3~5개 간결하게 정리
2. 다음 주 예고 (예정된 행사, 기대되는 소식 등)
3. "END NF 션입니다"로 시작, "다음 주도 함께해요"로 마무리
4. ⚠️ 각 소식에 날짜와 출처를 간략히 포함 (예: "2월 28일 CTF 발표 - ...")""",
    },
}


# ============================================================
# 특집 콘텐츠 프롬프트
# ============================================================
SPECIAL_PROMPTS = {
    "professor": {
        "title": "특집: 이범희 교수님 / 유전병 이야기",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
이범희 교수님(서울대 소아과/유전학)의 연구와 업적, 유전병 관련 심층 이야기를 전합니다.

{STYLE_GUIDE}

### 특집 가이드
- 이범희 교수님의 NF/유전병 연구 업적 소개
- 유전 상담의 중요성과 절차 안내
- 최신 유전학 치료 가이드라인 쉽게 설명
- 환자와 가족에게 전문가의 존재가 든든하다는 메시지
- 교수님에 대한 존경을 담되, 과도한 미화는 지양
- 해시태그: #이범희교수님 #유전상담 #NF유전학""",

        "user_template": """아래 이범희 교수님 관련 데이터를 바탕으로 END NF 카페 특집 포스팅을 작성해주세요.

[수집된 데이터]
{collected_data}

요구사항:
1. 교수님의 최근 연구나 업적 중심
2. 유전 상담/유전 검사에 대한 실용 정보 포함
3. 환자 가족에게 전문가가 함께하고 있다는 안심 메시지
4. "END NF 션입니다"로 시작""",
    },
}


# ============================================================
# 이미지 프롬프트 생성기
# ============================================================
IMAGE_PROMPT_GUIDE = """
아래 글 내용에 어울리는 이미지 생성용 영문 프롬프트를 작성해주세요.

### 이미지 프롬프트 규칙
- 영문으로 작성
- 따뜻하고 희망적인 분위기
- 의료/과학 + 인간적 따뜻함의 조합
- 밝은 색조 (파스텔, 따뜻한 색감)
- 부정적/무서운/어두운 이미지 금지
- 사실적 의료 사진보다는 일러스트/아트 스타일 선호
- 나노바나나 또는 그록에서 사용 가능한 상세한 프롬프트

출력 형식:
[이미지 설명] 이미지에 담길 내용 한글 설명
[프롬프트] 영문 이미지 생성 프롬프트
"""


# ============================================================
# 메인 생성기 클래스
# ============================================================
class ContentGenerator:
    """Claude API를 사용한 END NF 콘텐츠 생성기"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = None
        if HAS_ANTHROPIC and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    def _prepare_data_summary(self, items: list, max_items: int = 8) -> str:
        """수집 데이터를 Claude에게 전달할 요약문으로 변환"""
        if not items:
            return "(수집된 데이터가 없습니다. 일반적인 NF 응원/정보 글을 작성해주세요.)"

        # 관련성 높은 순으로 정렬
        sorted_items = sorted(items, key=lambda x: x.get("relevance_score", 0), reverse=True)
        top_items = sorted_items[:max_items]

        summaries = []
        for i, item in enumerate(top_items, 1):
            source = item.get("source_type", "unknown")
            title = item.get("title", "제목 없음")
            summary = item.get("summary", "")
            url = item.get("url", "")
            extra = ""

            if source == "pubmed":
                journal = item.get("journal", "")
                authors = ", ".join(item.get("authors", [])[:3])
                pub_date = item.get("pub_date", "")
                extra = f"  📅 날짜: {pub_date or '미확인'}\n  📰 출처: {journal} | 저자: {authors}"
            elif source == "clinical_trial":
                status = item.get("status", "")
                phase = item.get("phase", [])
                sponsor = item.get("sponsor", "")
                last_update = item.get("last_update", "")
                start_date = item.get("raw_data", {}).get("start_date", "")
                is_new = item.get("is_new_this_week", False)
                new_tag = " (🆕 이번 주 신규/업데이트)" if is_new else ""
                extra = f"  📅 최종업데이트: {last_update or '미확인'} | 시작일: {start_date or '미확인'}\n  📰 출처: ClinicalTrials.gov | 스폰서: {sponsor}\n  상태: {status} | 단계: {phase}{new_tag}"
            elif source == "news":
                source_name = item.get("source_name", "")
                pub_date = item.get("pub_date", "")
                extra = f"  📅 날짜: {pub_date or '미확인'}\n  📰 출처: {source_name or '미확인'}"
            elif source == "patient_story":
                positivity = item.get("positivity_score", 0)
                pub_date = item.get("pub_date", "")
                source_name = item.get("source_name", "")
                date_line = f"📅 날짜: {pub_date}" if pub_date else ""
                source_line = f"📰 출처: {source_name}" if source_name else "📰 출처: 해외 NF 커뮤니티"
                extra = f"  {date_line}\n  {source_line} | 긍정도: {positivity}/10" if date_line else f"  {source_line} | 긍정도: {positivity}/10"

            entry = f"[{i}] ({source}) {title}\n  요약: {summary}\n  URL: {url}"
            if extra:
                entry += f"\n{extra}"
            summaries.append(entry)

        return "\n\n".join(summaries)

    def generate(self, day: str, items: list, special: str = "") -> dict:
        """
        카페 포스팅 초안 생성

        Args:
            day: mon~sun
            items: 수집된 데이터 리스트 (정규화된 형식)
            special: 특집 타입 (professor 등)

        Returns:
            {content, image_prompt, metadata} 딕셔너리
        """
        # 프롬프트 선택
        if special and special in SPECIAL_PROMPTS:
            prompt_config = SPECIAL_PROMPTS[special]
        elif day in DAY_PROMPTS:
            prompt_config = DAY_PROMPTS[day]
        else:
            print(f"❌ 알 수 없는 요일/특집: {day}/{special}")
            return {}

        print(f"\n{'='*60}")
        print(f"✍️ 콘텐츠 생성: {prompt_config['title']}")
        print(f"   입력 데이터: {len(items)}건")
        print(f"{'='*60}")

        # 데이터 요약 준비
        data_summary = self._prepare_data_summary(items)

        # 사용자 프롬프트 조합
        user_message = prompt_config["user_template"].format(collected_data=data_summary)

        # 이미지 프롬프트 요청도 함께
        user_message += f"\n\n---\n\n추가로, 위 글에 어울리는 이미지도 제안해주세요.\n{IMAGE_PROMPT_GUIDE}"

        # Claude API 호출
        if not self.client:
            print("⚠️ Claude API 키가 없습니다. 미리보기 모드로 동작합니다.")
            return self._generate_preview(prompt_config, data_summary)

        try:
            print("  🤖 Claude API 호출 중...")
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=prompt_config["system"],
                messages=[
                    {"role": "user", "content": user_message}
                ],
            )

            content = response.content[0].text
            print(f"  ✅ 생성 완료 ({len(content)}자)")

            # 본문과 이미지 프롬프트 분리
            post_content, image_prompt = self._split_content_and_image(content)

            result = {
                "day": day,
                "special": special,
                "title": prompt_config["title"],
                "content": post_content,
                "image_prompt": image_prompt,
                "input_items_count": len(items),
                "model": MODEL,
                "generated_at": datetime.now().isoformat(),
                "tokens_used": {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                },
            }

            # 이미지 프롬프트도 별도 생성 (image_prompt_generator 연동)
            try:
                from image_prompt_generator import ImagePromptGenerator
                img_gen = ImagePromptGenerator()
                img_result = img_gen.generate(
                    day=day or "mon",
                    content_summary=post_content[:500],
                    platform="nanobana",
                    layout="single_image",
                )
                result["image_prompts_structured"] = img_result.get("prompts", [])
                result["negative_prompt"] = img_result.get("negative_prompt", "")
            except Exception as e:
                print(f"  ⚠️ 이미지 프롬프트 구조화 건너뜀: {e}")

            self._save_output(result)
            return result

        except Exception as e:
            print(f"  ❌ Claude API 호출 실패: {e}")
            return self._generate_preview(prompt_config, data_summary)

    def _split_content_and_image(self, full_text: str) -> tuple:
        """Claude 응답에서 본문과 이미지 프롬프트 분리"""
        # [이미지 설명] 또는 [프롬프트] 태그로 분리 시도
        markers = ["[이미지 설명]", "[이미지 프롬프트]", "[프롬프트]", "Image Prompt:", "이미지 프롬프트:"]
        
        for marker in markers:
            if marker in full_text:
                parts = full_text.split(marker, 1)
                post_content = parts[0].strip().rstrip("-").rstrip("─").strip()
                image_section = marker + parts[1]
                return post_content, image_section

        # 구분자를 못 찾으면 전체를 본문으로
        return full_text, "(이미지 프롬프트 별도 생성 필요)"

    def _generate_preview(self, prompt_config: dict, data_summary: str) -> dict:
        """API 없이 미리보기 생성"""
        preview = f"""[미리보기 모드 - API 키 설정 후 실제 생성]

━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 프롬프트: {prompt_config['title']}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

[시스템 프롬프트 요약]
- 스타일: "END NF 션입니다"로 시작
- 톤: 따뜻하고 전문적
- 형식: 글머리기호 없이 자연스러운 문장형

[입력 데이터]
{data_summary[:500]}...

[예상 출력]
END NF 션입니다 🙏

(이 자리에 수집된 데이터를 바탕으로 한 카페 포스팅이 생성됩니다)

END NF, 함께하면 이겨낼 수 있습니다 💙
#ENDNF #신경섬유종 #NF #희귀질환
━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💡 실제 생성하려면:
   export ANTHROPIC_API_KEY="your-key-here"
   python content_generator.py --day {prompt_config.get('day', 'mon')}
"""
        return {
            "day": "",
            "title": prompt_config["title"],
            "content": preview,
            "image_prompt": "(미리보기 모드)",
            "preview_mode": True,
            "generated_at": datetime.now().isoformat(),
        }

    def _save_output(self, result: dict):
        """생성 결과 저장"""
        date_str = datetime.now().strftime("%Y%m%d")
        day = result.get("day", "special")
        special = result.get("special", "")
        
        if special:
            filename = f"post_{special}_{date_str}.json"
        else:
            filename = f"post_{day}_{date_str}.json"

        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  💾 저장: {filepath}")

        # 카페 포스팅용 텍스트 파일도 저장
        txt_filename = filename.replace(".json", ".txt")
        txt_filepath = os.path.join(OUTPUT_DIR, txt_filename)
        with open(txt_filepath, "w", encoding="utf-8") as f:
            f.write(result.get("content", ""))
            if result.get("image_prompt") and result["image_prompt"] != "(미리보기 모드)":
                f.write(f"\n\n{'─'*40}\n")
                f.write(f"📷 이미지 프롬프트:\n{result['image_prompt']}")
        print(f"  📝 텍스트 저장: {txt_filepath}")

    def generate_from_daily_file(self, filepath: str, day: str = "") -> dict:
        """daily_runner.py 출력 파일에서 데이터 로드 후 생성"""
        print(f"📂 데이터 로드: {filepath}")

        with open(filepath, "r", encoding="utf-8") as f:
            daily_data = json.load(f)

        items = daily_data.get("items", [])
        detected_day = day or daily_data.get("day", "")

        if not detected_day:
            print("⚠️ 요일 정보 없음. --day 옵션으로 지정해주세요.")
            return {}

        return self.generate(detected_day, items)


def main():
    parser = argparse.ArgumentParser(description="END NF Claude API 콘텐츠 생성기")
    parser.add_argument("--day", type=str, default="",
                        help="요일 (mon~sun)")
    parser.add_argument("--input", type=str, default="",
                        help="입력 데이터 파일 (daily_runner.py 출력)")
    parser.add_argument("--special", type=str, default="",
                        help="특집 (professor)")
    parser.add_argument("--preview", action="store_true",
                        help="미리보기 모드 (API 호출 없이)")
    args = parser.parse_args()

    generator = ContentGenerator()

    # 미리보기 모드
    if args.preview:
        generator.client = None  # API 비활성화

    if args.input:
        # 특정 파일에서 로드
        result = generator.generate_from_daily_file(args.input, args.day)
    elif args.special:
        # 특집 콘텐츠
        # 이범희 교수님 데이터 로드 시도
        data_file = os.path.join(DATA_DIR, f"professor_lee_{datetime.now().strftime('%Y%m%d')}.json")
        items = []
        if os.path.exists(data_file):
            with open(data_file, "r", encoding="utf-8") as f:
                items = json.load(f)
        result = generator.generate("", items, special=args.special)
    else:
        # 오늘 데이터 파일 자동 탐색
        today_file = os.path.join(DATA_DIR, f"daily_{datetime.now().strftime('%Y%m%d')}.json")
        if os.path.exists(today_file):
            result = generator.generate_from_daily_file(today_file, args.day)
        else:
            # 데이터 없이 생성 (일반 응원 글)
            day = args.day
            if not day:
                from daily_runner import get_today_day
                day = get_today_day()
            result = generator.generate(day, [])

    # 결과 출력
    if result:
        content = result.get("content", "")
        print(f"\n{'━'*60}")
        print("📋 생성된 콘텐츠 미리보기:")
        print(f"{'━'*60}")
        print(content[:800])
        if len(content) > 800:
            print(f"... ({len(content)}자 중 800자까지 표시)")
        print(f"{'━'*60}")


if __name__ == "__main__":
    main()
