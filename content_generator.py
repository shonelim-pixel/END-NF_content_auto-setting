"""
============================================================
END NF 콘텐츠 시스템 v2 - Claude API 글 자동 생성기
============================================================
3개 콘텐츠 타입: story(우리의 이야기), info(알아두면 좋은 소식), welfare(복지 가이드)

사용법:
    python content_generator.py --type story              # 화요일: 우리의 이야기
    python content_generator.py --type info --week 1      # 금요일: 1주차 NF 연구
    python content_generator.py --type welfare --topic 1  # 특별편: 산정특례 가이드
    python content_generator.py --type story --preview    # 미리보기 (API 호출 없이)

환경변수:
    ANTHROPIC_API_KEY: Claude API 키 (필수)
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
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
# 공통 스타일 가이드
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

### 날짜·출처 필수 표기 규칙
- 모든 연구, 뉴스, 임상시험 소식에는 반드시 발표/게시 날짜를 함께 적어야 합니다
- 예: "2026년 2월 발표된 연구에 따르면...", "지난 3월 1일 CTF에서 발표한 소식으로는..."
- 출처(저널명, 매체명, 기관명)도 반드시 자연스럽게 본문에 포함
- 수집 데이터에 날짜(📅)와 출처 정보가 함께 제공됩니다. 반드시 활용하세요

### 심리 힐링 — 두 종류의 독자를 항상 떠올리세요
1. 막 진단받아서 세상이 무너진 것 같은 부모
2. 오랜 투병으로 희망이 사라진 환자/가족
이 두 사람이 글을 읽었을 때 조금이라도 마음이 나아져야 합니다.

절대 하지 말 것:
- "힘내세요"만 반복하는 빈 위로
- 비현실적인 희망 ("곧 완치됩니다" 등)
- 성공 영웅담으로 부담 주기

반드시 할 것:
- "당신만 그런 게 아닙니다" 메시지
- 실제 경험에서 나온 구체적인 위로
- 작은 희망이라도 근거 있는 희망
- "당신의 마음도 소중합니다" (보호자 번아웃 해소)

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
"""


# ============================================================
# 콘텐츠 타입별 프롬프트 (v2: story / info / welfare)
# ============================================================
TYPE_PROMPTS = {
    # ── 1회차: 우리의 이야기 (화요일) ──
    "story": {
        "title": "💛 우리의 이야기",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
환자와 가족에게 진짜 힘이 되는 이야기를 전합니다.

{STYLE_GUIDE}

### 1회차 "우리의 이야기" 특화 가이드

콘텐츠 유형 (수집된 데이터에 따라 자동 선택):
A. "처음엔 나도 그랬어요" — 진단 이야기 (진단 직후 충격→극복)
B. "아이가 웃는 순간들" — 질환이 전부가 아닌 일상, 작은 성취
C. "함께라서 괜찮아요" — 커뮤니티의 힘, 모임의 가치
D. "마음이 힘들 때" — 실제 대처법, 간병 피로, 가족 소통
E. 영화·책·미디어 속 희귀질환/다름 이야기 (공감 포인트 중심)
F. 해외 커뮤니티·이벤트 소식 (글로벌 연대감)

핵심 원칙:
- 해외 이야기는 한국 독자에 맞게 재구성 (직접 번역이 아닌 핵심 메시지 전달)
- 환자의 용기와 강인함을 부각하되, 영웅담이 아닌 현실적 이야기
- "지금도 가끔 힘들지만, 이렇게 지내고 있어요" 톤
- 아이 관련: "걱정보다 사랑과 행복을 선물해주세요"
- 글 마지막에 반드시: "처음 진단받으셨나요? 혼자 고민하지 마세요. END NF 카페에 질문을 남겨주시면 선배 가족이 답해드립니다."

해시태그: #ENDNF #신경섬유종 #NF #희귀질환 #함께해요 #NF환우""",

        "user_template": """아래 수집된 데이터를 바탕으로 END NF 카페 포스팅 초안을 작성해주세요.

[수집된 데이터]
{collected_data}

[콘텐츠 유형 힌트]
{story_type_hint}

요구사항:
1. 가장 감동적이고 공감이 되는 이야기 1개를 중심으로 작성
2. 위 콘텐츠 유형(A~F) 중 가장 적합한 것으로 자연스럽게 풀어주세요
3. 해외 스토리는 한국 환우 가족이 공감할 수 있게 재구성
4. "END NF 션입니다"로 시작
5. 글 마지막에 "처음 진단받으셨나요?" 안내 포함
6. 이야기의 출처를 자연스럽게 언급 (예: "CTF에 소개된 한 가족의 이야기입니다")
7. 날짜 정보가 있으면 반드시 포함""",
    },

    # ── 2회차: 알아두면 좋은 소식 (금요일, 월별 로테이션) ──
    "info": {
        "title": "💡 알아두면 좋은 소식",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
최신 연구·치료·글로벌 소식을 환자와 가족이 이해할 수 있게 전합니다.

{STYLE_GUIDE}

### 2회차 "알아두면 좋은 소식" 특화 가이드

월별 로테이션 (자동 전환):
- 1주차: NF 연구·신약·임상시험
- 2주차: 유전질환 치료 연구 동향 (CRISPR, 유전자치료 등)
- 3주차: CTF·글로벌 NF 소식
- 4주차: 그 달에 더 새로운 소식이 있는 쪽

핵심 원칙:
- 논문/임상시험의 핵심을 비전문가도 이해할 수 있게 설명
- 어려운 의학 용어는 괄호 안에 쉬운 설명 추가
- "이 연구가 환자들에게 어떤 의미인지" 반드시 포함
- 과도한 기대 없이 현실적이되, 희망을 잃지 않게
- 임상시험 단계(Phase 1/2/3) 쉽게 설명
- 한국 환자에게의 의미/접근성도 언급
- 유전질환 관련: NF와의 연결고리 필수 ("이 기술이 NF 치료에도 희망이 됩니다")
- 🆕 표시된 신규 항목은 최우선으로 다루기
- 레어노트, CTF 뉴스 등 참고처 자연스럽게 언급

해시태그: #ENDNF #신경섬유종 #NF #희귀질환 #NF연구 #임상시험""",

        "user_template": """아래 수집된 데이터를 바탕으로 END NF 카페 포스팅 초안을 작성해주세요.

[이번 주 로테이션 주제]
{rotation_topic}

[수집된 데이터]
{collected_data}

요구사항:
1. 가장 의미 있는 소식 1~2개를 선정해서 중심 내용으로 작성
2. 환자/보호자가 "이게 나한테 어떤 의미인지" 바로 이해할 수 있게
3. 의학 용어는 쉽게 풀어서 설명
4. "END NF 션입니다"로 시작, 따뜻한 마무리
5. 각 연구/뉴스의 발표 날짜와 출처를 본문에 반드시 포함
6. 🆕 표시된 신규 항목은 "이번 주 새로운 소식"으로 강조""",
    },

    # ── 특별편: 복지 가이드 시리즈 ──
    "welfare": {
        "title": "📋 복지 가이드 시리즈",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
희귀질환 환자와 가족을 위한 상세한 복지/정책 실용 가이드를 작성합니다.

{STYLE_GUIDE}

### 특별편 "복지 가이드" 특화 가이드

핵심 원칙:
- NF뿐 아니라 희귀질환·의료 복지 전반을 다룸
- 환자/보호자가 바로 활용할 수 있는 실용 정보 위주
- 신청 절차, 필요 서류, 연락처, 기한 등 구체적 안내
- "이 제도가 우리에게 어떤 혜택이 있는지" 명확하게
- 복잡한 법/제도를 쉽고 친근하게 설명
- 2026년 기준 최신 정보 반영
- 글머리기호 대신 자연스러운 문장으로 정리 (단, 절차/서류 안내는 예외적으로 가능)

글 분량: 복지 가이드는 1500~2500자 (일반 콘텐츠보다 상세하게)

해시태그: #ENDNF #신경섬유종 #희귀질환 #ENDNF복지가이드 #희귀질환복지 #의료비지원""",

        "user_template": """아래 주제에 대한 END NF 카페 복지 가이드 특별편을 작성해주세요.

[이번 회차 주제]
{welfare_topic}

[참고 데이터]
{collected_data}

요구사항:
1. 해당 복지 제도를 환자/보호자 관점에서 상세하게 안내
2. 신청 절차, 필요 서류, 자격 요건 등을 구체적으로
3. 관련 기관 연락처나 웹사이트 안내
4. "END NF 션입니다"로 시작
5. 출처 정보(보건복지부, 건강보험심사평가원 등) 명시
6. 2026년 기준 최신 정보 반영
7. 마지막에 "궁금한 점은 카페에 질문 남겨주세요" 안내""",
    },

    # ── 교육 시리즈 (2회차 폴백) ──
    "education": {
        "title": "💡 알아두면 좋은 소식 — 교육 시리즈",
        "system": f"""당신은 END NF(신경섬유종 환우회)의 공식 카페 콘텐츠 작성자 "션"입니다.
NF 관련 의학/과학 지식을 쉽고 따뜻하게 설명합니다.

{STYLE_GUIDE}

### 교육 시리즈 특화 가이드
- 특정 의학/과학 주제를 비전문가도 이해할 수 있게 설명
- 일상적 비유를 활용하여 쉽게 풀어주세요
- "왜 이걸 알아야 하는지"를 먼저 설명 → 내용 전개
- 환자/가족이 "아하, 그런 거구나!" 하고 이해할 수 있는 수준

해시태그: #ENDNF #신경섬유종 #NF #희귀질환 #NF교육 #알아두면좋은정보""",

        "user_template": """아래 주제에 대한 END NF 카페 교육 시리즈를 작성해주세요.

[주제]
{education_topic}

[참고 데이터 (있으면)]
{collected_data}

요구사항:
1. 해당 주제를 쉽고 따뜻하게 설명
2. 일상적 비유로 이해도 높이기
3. "END NF 션입니다"로 시작
4. 참고 자료 출처 명시""",
    },
}


# ============================================================
# 복지 가이드 시리즈 목록 (12회)
# ============================================================
WELFARE_TOPICS = {
    1: "산정특례 신청 완전 가이드 — 대상 질환(2026년 1,389개), 신청 절차, 필요 서류, 5년 재등록 간소화",
    2: "2026년 달라지는 의료 복지 총정리 — 본인부담률 10%→5% 인하, 치료제 급여 등재 240→100일 단축, 부양의무자 기준 단계적 폐지",
    3: "희귀질환 의료비 지원사업 — 본인부담금 지원, 간병비, 특수식이 비용, 소득 기준, 신청 방법",
    4: "장애등록과 장애인 복지 — 장애등록 절차, 장애등급 판정, 의료비 감면, 보조기기 지원",
    5: "아이를 위한 교육·돌봄 지원 — 특수교육 대상자 지정, 장애아 돌봄 서비스, 보육료 지원, 발달재활 바우처",
    6: "긴급복지 지원제도 — 위기상황 시 긴급 의료비·생활비 지원, 신청 방법",
    7: "유전 상담과 검사 안내 — 유전 상담이란, 어디서 받나, 비용, NF 유전 검사 종류",
    8: "간병·돌봄 가족을 위한 지원 — 가족 돌봄 휴가, 간병인 지원, 심리 상담, 가족 쉼터",
    9: "건강보험·실비보험 청구 가이드 — 실비보험 청구 방법, 산정특례 환자 보험 활용, 비급여 항목",
    10: "해외 치료를 위한 지원제도 — 해외 치료비 지원, 건강보험 적용, 출국 전 준비",
    11: "2026 건강보험 종합계획 핵심 정리 — 건강보험료율 7.19%, 의료-복지 연계 포괄 지원체계",
    12: "마음 건강을 위한 지원 — 환자와 가족 심리 상담 서비스, 정신건강복지센터, 자조모임 안내",
}


# ============================================================
# 교육 시리즈 목록 (2회차 폴백용)
# ============================================================
EDUCATION_TOPICS = {
    "edu-001": "MEK 억제제, 쉽게 알려드릴게요 — Koselugo(셀루메티닙)가 어떻게 작용하는지, 비유로 쉽게",
    "edu-002": "임상시험은 어떤 단계를 거치나요? — Phase 1/2/3의 차이, 왜 오래 걸리는지",
    "edu-003": "AI가 신약을 찾는다고요? — CTF-Healx AI 신약 발견 프로젝트 이야기",
    "edu-004": "신약이 환자에게 오기까지의 여정 — 연구실에서 약국까지, 10~15년의 과정",
    "edu-005": "CRISPR 유전자 가위란? — NF 치료의 미래 가능성",
    "edu-006": "RAS 경로와 NF1 — 왜 NF1이 생기는지, 쉽게 이해하기",
    "edu-007": "유전자 치료(Gene Therapy)의 현재와 미래 — 희귀질환 치료의 새 희망",
    "edu-008": "희귀질환 신약 개발, 왜 이렇게 어려울까? — 오펀 드럭 제도와 인센티브",
}


# ============================================================
# 에버그린 콘텐츠 (1회차 폴백용)
# ============================================================
EVERGREEN_TOPICS = {
    "eg-001": {"type": "A", "title": "NF 진단을 받은 날, 그리고 1년 후", "prompt": "NF 진단을 처음 받은 가족이 겪는 감정의 변화와, 1년이 지난 후 어떻게 달라졌는지를 따뜻하게 그려주세요. 진단 직후의 충격, 눈물, 검색의 공포, 그리고 시간이 지나며 찾아온 일상과 작은 희망들."},
    "eg-002": {"type": "D", "title": "검색을 멈추고 아이를 안아주세요", "prompt": "밤마다 NF를 검색하며 불안해하는 부모에게 전하는 이야기. 검색을 멈추기로 결심한 순간, 아이와 눈을 마주친 순간의 따뜻함. 정보도 중요하지만 지금 이 순간 아이에게 필요한 건 엄마 아빠의 웃는 얼굴이라는 메시지."},
    "eg-003": {"type": "B", "title": "학교에서 아이를 위해 할 수 있는 것들", "prompt": "NF 아이의 학교생활, 선생님과의 소통, 친구 관계에서 부모가 할 수 있는 구체적인 것들. 실제 경험에서 나온 팁 중심."},
    "eg-004": {"type": "D", "title": "간병하는 가족의 마음도 소중합니다", "prompt": "아이를 돌보느라 자신의 마음은 뒷전인 부모에게 전하는 위로. 간병 피로, 부부간 갈등, 혼자 우는 밤. 자신을 돌보는 것이 아이를 위한 것이기도 하다는 메시지."},
    "eg-005": {"type": "B", "title": "NF 아이와 함께하는 특별한 일상", "prompt": "NF가 있지만 평범하고 행복한 일상을 보내는 아이들의 이야기. 좋아하는 것을 찾은 순간, 친구와 웃는 순간, 작은 성취의 기쁨."},
    "eg-006": {"type": "C", "title": "혼자 울던 밤에서, 함께 웃는 오늘까지", "prompt": "혼자 고민하다 환우회를 찾은 후 달라진 이야기. 처음 카페에 글을 올렸던 날, 같은 처지의 부모를 만난 날, '나만 그런 게 아니었구나'를 느낀 순간."},
    "eg-007": {"type": "E", "title": "영화 '원더'가 NF 가족에게 전하는 메시지", "prompt": "영화 '원더'를 NF 가족의 시선으로 다시 보기. 어기의 이야기가 NF 아이와 얼마나 닮아있는지, 어떤 장면에서 눈물이 났는지, 이 영화가 전하는 진짜 메시지."},
    "eg-008": {"type": "D", "title": "부부가 함께 NF를 이겨내는 법", "prompt": "아이의 질환 앞에서 부부가 겪는 갈등과 소통의 어려움. 서로를 탓하던 시간에서 함께 버텨온 시간으로. 부부 상담, 대화법, 서로의 감정을 인정하는 것의 중요성."},
    "eg-009": {"type": "B", "title": "형제자매에게 NF를 설명하는 방법", "prompt": "NF 아이의 형제자매가 느끼는 소외감, 궁금증, 걱정. 어떻게 설명하면 좋을지, 형제자매도 함께 돌봐야 한다는 메시지."},
    "eg-010": {"type": "D", "title": "마음이 무너질 때 도움받을 수 있는 곳", "prompt": "심리적으로 힘들 때 활용할 수 있는 자원들. 정신건강복지센터, 자조모임, 온라인 상담, 가족 쉼터 등 구체적 안내. 도움을 요청하는 것은 약한 게 아니라 용기라는 메시지."},
}


# ============================================================
# 이미지 프롬프트 가이드
# ============================================================
IMAGE_PROMPT_GUIDE = """
아래 글 내용에 어울리는 이미지 생성용 영문 프롬프트를 작성해주세요.

### 이미지 프롬프트 규칙
- 영문으로 작성
- 따뜻하고 희망적인 분위기
- 의료/과학 + 인간적 따뜻함의 조합
- 밝은 색조 (파스텔, 따뜻한 색감)
- 부정적/무서운/어두운 이미지 금지
- 일러스트/아트 스타일 선호

출력 형식:
[이미지 설명] 이미지에 담길 내용 한글 설명
[프롬프트] 영문 이미지 생성 프롬프트
"""


# ============================================================
# 메인 생성기 클래스
# ============================================================
class ContentGenerator:
    """Claude API를 사용한 END NF 콘텐츠 생성기 v2"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        self.client = None
        if HAS_ANTHROPIC and self.api_key:
            self.client = anthropic.Anthropic(api_key=self.api_key)

    def _prepare_data_summary(self, items: list, max_items: int = 8) -> str:
        """수집 데이터를 Claude에게 전달할 요약문으로 변환"""
        if not items:
            return "(수집된 데이터가 없습니다. 에버그린/교육 콘텐츠를 작성해주세요.)"

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

    def generate(self, content_type: str, items: list, **kwargs) -> dict:
        """
        카페 포스팅 초안 생성

        Args:
            content_type: story, info, welfare, education
            items: 수집된 데이터 리스트
            **kwargs: rotation_topic, welfare_topic, story_type_hint, education_topic, evergreen_id
        """
        # 에버그린 콘텐츠 처리
        evergreen_id = kwargs.get("evergreen_id", "")
        if evergreen_id and evergreen_id in EVERGREEN_TOPICS:
            return self._generate_evergreen(evergreen_id, items)

        # 프롬프트 선택
        prompt_config = TYPE_PROMPTS.get(content_type)
        if not prompt_config:
            print(f"❌ 알 수 없는 콘텐츠 타입: {content_type}")
            return {}

        print(f"\n{'='*60}")
        print(f"✍️ 콘텐츠 생성: {prompt_config['title']}")
        print(f"   타입: {content_type}")
        print(f"   입력 데이터: {len(items)}건")
        print(f"{'='*60}")

        # 데이터 요약 준비
        data_summary = self._prepare_data_summary(items)

        # 사용자 프롬프트 조합
        user_message = prompt_config["user_template"].format(
            collected_data=data_summary,
            rotation_topic=kwargs.get("rotation_topic", ""),
            welfare_topic=kwargs.get("welfare_topic", ""),
            story_type_hint=kwargs.get("story_type_hint", "데이터에 가장 적합한 유형을 자동으로 선택해주세요."),
            education_topic=kwargs.get("education_topic", ""),
        )

        # 이미지 프롬프트 요청도 함께
        user_message += f"\n\n---\n\n추가로, 위 글에 어울리는 이미지도 제안해주세요.\n{IMAGE_PROMPT_GUIDE}"

        # Claude API 호출
        if not self.client:
            print("⚠️ Claude API 키가 없습니다. 미리보기 모드로 동작합니다.")
            return self._generate_preview(prompt_config, data_summary, content_type)

        try:
            print("  🤖 Claude API 호출 중...")
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=prompt_config["system"],
                messages=[{"role": "user", "content": user_message}],
            )

            content = response.content[0].text
            print(f"  ✅ 생성 완료 ({len(content)}자)")

            post_content, image_prompt = self._split_content_and_image(content)

            result = {
                "content_type": content_type,
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
                "kwargs": {k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool))},
            }

            # 이미지 프롬프트 구조화 시도
            try:
                from image_prompt_generator import ImagePromptGenerator
                img_gen = ImagePromptGenerator()
                img_result = img_gen.generate(
                    day="tue" if content_type == "story" else "fri",
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
            return self._generate_preview(prompt_config, data_summary, content_type)

    def _generate_evergreen(self, eg_id: str, items: list) -> dict:
        """에버그린 콘텐츠 생성"""
        eg = EVERGREEN_TOPICS[eg_id]
        print(f"\n🌿 에버그린 콘텐츠 생성: {eg['title']}")

        prompt_config = TYPE_PROMPTS["story"]
        data_summary = self._prepare_data_summary(items)

        user_message = f"""아래 주제에 대한 END NF 카페 포스팅을 작성해주세요.

[주제]
{eg['title']}

[글 방향]
{eg['prompt']}

[참고 데이터 (있으면)]
{data_summary}

요구사항:
1. 위 주제와 방향에 맞게 따뜻한 글 작성
2. "END NF 션입니다"로 시작
3. 글 마지막에 "처음 진단받으셨나요?" 안내 포함
4. 실제 경험에서 나온 듯한 생생하고 공감되는 이야기로

---

추가로, 위 글에 어울리는 이미지도 제안해주세요.
{IMAGE_PROMPT_GUIDE}"""

        if not self.client:
            return self._generate_preview(prompt_config, data_summary, "story")

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=prompt_config["system"],
                messages=[{"role": "user", "content": user_message}],
            )
            content = response.content[0].text
            post_content, image_prompt = self._split_content_and_image(content)

            result = {
                "content_type": "story",
                "sub_type": "evergreen",
                "evergreen_id": eg_id,
                "title": f"💛 우리의 이야기 — {eg['title']}",
                "content": post_content,
                "image_prompt": image_prompt,
                "model": MODEL,
                "generated_at": datetime.now().isoformat(),
                "tokens_used": {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                },
            }
            self._save_output(result)
            return result
        except Exception as e:
            print(f"  ❌ 에버그린 생성 실패: {e}")
            return {}

    def _split_content_and_image(self, full_text: str) -> tuple:
        """Claude 응답에서 본문과 이미지 프롬프트 분리"""
        markers = ["[이미지 설명]", "[이미지 프롬프트]", "[프롬프트]", "Image Prompt:", "이미지 프롬프트:"]
        for marker in markers:
            if marker in full_text:
                parts = full_text.split(marker, 1)
                post_content = parts[0].strip().rstrip("-").rstrip("─").strip()
                image_section = marker + parts[1]
                return post_content, image_section
        return full_text, "(이미지 프롬프트 별도 생성 필요)"

    def _generate_preview(self, prompt_config: dict, data_summary: str, content_type: str) -> dict:
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
   python content_generator.py --type {content_type}
"""
        return {
            "content_type": content_type,
            "title": prompt_config["title"],
            "content": preview,
            "image_prompt": "(미리보기 모드)",
            "preview_mode": True,
            "generated_at": datetime.now().isoformat(),
        }

    def _save_output(self, result: dict):
        """생성 결과 저장"""
        kst = timezone(timedelta(hours=9))
        date_str = datetime.now(kst).strftime("%Y%m%d")
        content_type = result.get("content_type", "unknown")
        filename = f"post_{content_type}_{date_str}.json"

        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"  💾 저장: {filepath}")

        # 카페 포스팅용 텍스트 파일도 저장
        txt_filepath = filepath.replace(".json", ".txt")
        with open(txt_filepath, "w", encoding="utf-8") as f:
            f.write(result.get("content", ""))
            if result.get("image_prompt") and result["image_prompt"] != "(미리보기 모드)":
                f.write(f"\n\n{'─'*40}\n")
                f.write(f"📷 이미지 프롬프트:\n{result['image_prompt']}")
        print(f"  📝 텍스트 저장: {txt_filepath}")

    def generate_from_daily_file(self, filepath: str, content_type: str = "", **kwargs) -> dict:
        """daily_runner.py 출력 파일에서 데이터 로드 후 생성"""
        print(f"📂 데이터 로드: {filepath}")
        with open(filepath, "r", encoding="utf-8") as f:
            daily_data = json.load(f)

        items = daily_data.get("items", [])
        ct = content_type or daily_data.get("content_type", "story")
        return self.generate(ct, items, **kwargs)


def main():
    parser = argparse.ArgumentParser(description="END NF Claude API 콘텐츠 생성기 v2")
    parser.add_argument("--type", type=str, default="",
                        help="콘텐츠 타입 (story/info/welfare/education)")
    parser.add_argument("--week", type=int, default=0,
                        help="로테이션 주차 (info 타입에서 사용, 1~4)")
    parser.add_argument("--topic", type=int, default=0,
                        help="복지 가이드 회차 (welfare 타입에서 사용, 1~12)")
    parser.add_argument("--input", type=str, default="",
                        help="입력 데이터 파일 (daily_runner.py 출력)")
    parser.add_argument("--preview", action="store_true",
                        help="미리보기 모드 (API 호출 없이)")
    # 하위 호환: --day 옵션도 지원
    parser.add_argument("--day", type=str, default="",
                        help="(하위호환) 요일 → 타입 자동 변환 (tue→story, fri→info)")
    args = parser.parse_args()

    generator = ContentGenerator()
    if args.preview:
        generator.client = None

    # --day 하위 호환
    content_type = args.type
    if not content_type and args.day:
        day_to_type = {"tue": "story", "fri": "info", "mon": "info", "thu": "info"}
        content_type = day_to_type.get(args.day, "story")

    kwargs = {}
    if args.week:
        rotation_map = {1: "🔬 1주차: NF 연구·신약·임상시험", 2: "🧬 2주차: 유전질환 치료 연구 동향",
                        3: "🌍 3주차: CTF·글로벌 NF 소식", 4: "🔬/🧬 4주차: 교차 주제"}
        kwargs["rotation_topic"] = rotation_map.get(args.week, "")

    if args.topic and args.topic in WELFARE_TOPICS:
        kwargs["welfare_topic"] = WELFARE_TOPICS[args.topic]
        content_type = "welfare"

    if args.input:
        result = generator.generate_from_daily_file(args.input, content_type, **kwargs)
    else:
        kst = timezone(timedelta(hours=9))
        today_file = os.path.join(DATA_DIR, f"daily_{datetime.now(kst).strftime('%Y%m%d')}.json")
        if os.path.exists(today_file):
            result = generator.generate_from_daily_file(today_file, content_type, **kwargs)
        else:
            if not content_type:
                content_type = "story"
            result = generator.generate(content_type, [], **kwargs)

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
