"""
============================================================
END NF 콘텐츠 시스템 - 이미지 프롬프트 자동 생성기 (4단계)
============================================================
요일별 콘텐츠에 어울리는 이미지 생성 프롬프트를 자동으로 만듭니다.
나노바나나(Nano Banana)와 그록(Grok) 이미지 생성기에 최적화.

사용법:
    python image_prompt_generator.py --day mon                  # 월요일 이미지 프롬프트
    python image_prompt_generator.py --day thu --style card      # 카드뉴스 스타일
    python image_prompt_generator.py --input output/post_thu_20260301.json  # 기존 글 기반
    python image_prompt_generator.py --day all --preview         # 전체 요일 미리보기

플랫폼:
    나노바나나: https://nanobana.na  (한국어 지원, 일러스트 강점)
    그록 (xAI): Grok Image Gen (사실적 + 아트 스타일)
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "output")
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================
# 글로벌 비주얼 가이드 (END NF 브랜드)
# ============================================================
BRAND_VISUAL = {
    "colors": {
        "primary": "#4A90D9",       # 신뢰의 블루
        "warm": "#F5A623",          # 따뜻한 오렌지/옐로우
        "hope": "#7ED321",          # 희망의 그린
        "soft_pink": "#F8B4C8",     # 부드러운 핑크
        "lavender": "#B8A9E8",      # 차분한 라벤더
        "background": "#FFF8F0",    # 따뜻한 아이보리 배경
        "accent_teal": "#50C8C6",   # NF 인식 리본 컬러 (teal)
    },
    "mood": "warm, hopeful, supportive, gentle, inclusive",
    "avoid": [
        "dark or gloomy atmospheres",
        "medical gore or realistic tumors",
        "sad or crying people",
        "hospital beds or clinical settings (unless warm)",
        "isolated or lonely figures",
        "scary or threatening imagery",
    ],
    "prefer": [
        "soft pastel color palettes",
        "warm lighting (golden hour feel)",
        "people together (family, community)",
        "nature elements (flowers, trees, sunrise)",
        "gentle illustration style",
        "abstract representations of hope and connection",
        "children playing happily",
        "hands holding or supporting",
    ],
}


# ============================================================
# 요일별 비주얼 스타일
# ============================================================
DAY_VISUAL_STYLES = {
    "mon": {
        "theme": "Science & Discovery",
        "mood": "intellectual curiosity meets warmth",
        "palette": "blue + white + soft gold accents",
        "elements": [
            "DNA helix with warm glow",
            "microscope with soft light",
            "open book with floating particles",
            "abstract neural network patterns",
            "researcher in warm lab setting",
        ],
        "style_keywords": "scientific illustration, soft watercolor, educational infographic feel",
        "hashtag_visual": "🔬📚",
    },
    "tue": {
        "theme": "Heart & Community",
        "mood": "warmth, love, togetherness",
        "palette": "soft pink + warm orange + cream",
        "elements": [
            "family embracing with warm light",
            "parent holding child's hand",
            "heart-shaped elements in nature",
            "warm sunset with silhouettes",
            "butterflies symbolizing transformation",
        ],
        "style_keywords": "warm illustration, soft pastel, children's book style, emotional",
        "hashtag_visual": "💛🤗",
    },
    "wed": {
        "theme": "Global Connection",
        "mood": "unity, solidarity, worldwide community",
        "palette": "teal (NF awareness) + blue + green earth tones",
        "elements": [
            "world map with connected lights",
            "diverse hands joining together",
            "NF awareness teal ribbon",
            "globe with warm glow",
            "bridge connecting communities",
        ],
        "style_keywords": "modern flat illustration, global feel, connected, diverse",
        "hashtag_visual": "🌍🤝",
    },
    "thu": {
        "theme": "Treatment & Hope",
        "mood": "breakthrough, progress, careful optimism",
        "palette": "teal + green + white clinical-but-warm",
        "elements": [
            "pill or medicine with soft glow of hope",
            "laboratory flask with light inside",
            "path leading to bright horizon",
            "puzzle pieces coming together",
            "seedling growing through stone",
        ],
        "style_keywords": "hopeful medical illustration, clean design, progress metaphor",
        "hashtag_visual": "💊🔬",
    },
    "fri": {
        "theme": "Policy & Support",
        "mood": "protection, institutional support, empowerment",
        "palette": "blue + gold + warm white",
        "elements": [
            "protective umbrella over family",
            "official document with warm seal",
            "shield with heart symbol",
            "stepping stones leading forward",
            "open door with light streaming in",
        ],
        "style_keywords": "clean infographic, institutional warmth, protective, structured",
        "hashtag_visual": "📋🏛️",
    },
    "sat": {
        "theme": "Healing & Daily Life",
        "mood": "peaceful, restful, everyday joy",
        "palette": "lavender + soft green + warm cream",
        "elements": [
            "person in nature with peaceful expression",
            "cup of tea with steam rising",
            "yoga or meditation gentle pose",
            "garden with blooming flowers",
            "cat napping in sunlight",
        ],
        "style_keywords": "zen illustration, cozy, mindfulness, lifestyle art, hygge feel",
        "hashtag_visual": "🌿☕",
    },
    "sun": {
        "theme": "Weekly Wrap & Look Ahead",
        "mood": "reflection, gratitude, anticipation",
        "palette": "sunset orange + purple + warm gold",
        "elements": [
            "open journal with highlights",
            "sunrise/sunset over calm landscape",
            "calendar with warm checkmarks",
            "road stretching into golden horizon",
            "collage of week's moments",
        ],
        "style_keywords": "editorial illustration, warm recap feel, magazine style",
        "hashtag_visual": "📰🌅",
    },
    "special_professor": {
        "theme": "Expert & Genetics",
        "mood": "trust, expertise, caring science",
        "palette": "navy + gold + white + warm accent",
        "elements": [
            "DNA strand with warm golden glow",
            "stethoscope with heart",
            "wise figure with gentle expression",
            "genetic tree diagram softly illustrated",
            "medical textbook open to genetics chapter",
        ],
        "style_keywords": "professional medical illustration, warm academic, trustworthy",
        "hashtag_visual": "🧬👨‍⚕️",
    },
}


# ============================================================
# 플랫폼별 프롬프트 최적화
# ============================================================
PLATFORM_TEMPLATES = {
    "nanobana": {
        "name": "나노바나나",
        "prefix": "",
        "suffix": ", high quality, detailed, 4K",
        "style_map": {
            "illustration": "digital illustration style",
            "watercolor": "soft watercolor painting style",
            "flat": "modern flat design illustration",
            "infographic": "clean infographic design",
            "pastel": "soft pastel art style",
            "editorial": "editorial magazine illustration",
        },
        "aspect_ratios": {
            "square": "1:1",       # 카페 포스팅 기본
            "card": "3:4",         # 카드뉴스
            "banner": "16:9",      # 배너형
            "story": "9:16",       # 인스타 스토리
        },
        "tips": [
            "한국어 키워드도 잘 인식 (예: '따뜻한 가족')",
            "색상 hex 코드 직접 지정 가능",
            "네거티브 프롬프트로 원치 않는 요소 제거",
        ],
    },
    "grok": {
        "name": "그록 (xAI)",
        "prefix": "",
        "suffix": ", professional quality, visually appealing",
        "style_map": {
            "illustration": "digital art illustration",
            "watercolor": "watercolor painting aesthetic",
            "flat": "flat vector illustration",
            "infographic": "infographic design layout",
            "pastel": "soft pastel color palette artwork",
            "editorial": "editorial illustration style",
        },
        "aspect_ratios": {
            "square": "1:1",
            "card": "3:4",
            "banner": "16:9",
            "story": "9:16",
        },
        "tips": [
            "영문 프롬프트 우선 사용",
            "구체적 장면 묘사가 효과적",
            "스타일 레퍼런스 아티스트 언급 가능",
        ],
    },
}


# ============================================================
# 카드뉴스 레이아웃 템플릿
# ============================================================
CARD_NEWS_LAYOUTS = {
    "single_image": {
        "name": "단일 이미지",
        "description": "메인 이미지 1장 (카페 포스팅 대표 이미지)",
        "count": 1,
        "layout_prompt": "single hero image, centered composition, clean background",
    },
    "card_3": {
        "name": "3장 카드뉴스",
        "description": "표지 + 본문 + 마무리",
        "count": 3,
        "slides": [
            {"role": "cover", "prompt_add": "title card, bold typography space at top, eye-catching"},
            {"role": "content", "prompt_add": "informational layout, space for text overlay, clean composition"},
            {"role": "closing", "prompt_add": "warm closing image, community feel, END NF branding space"},
        ],
    },
    "card_5": {
        "name": "5장 카드뉴스",
        "description": "표지 + 본문3 + 마무리",
        "count": 5,
        "slides": [
            {"role": "cover", "prompt_add": "title card, bold typography space, attention-grabbing"},
            {"role": "key_point_1", "prompt_add": "first key point visual, icon-style, clean"},
            {"role": "key_point_2", "prompt_add": "second key point visual, data visualization feel"},
            {"role": "key_point_3", "prompt_add": "third key point visual, human element"},
            {"role": "closing", "prompt_add": "warm closing, call to action, community gathering feel"},
        ],
    },
}


# ============================================================
# 이미지 프롬프트 생성기 클래스
# ============================================================
class ImagePromptGenerator:
    """요일별 맞춤 이미지 프롬프트 생성"""

    def __init__(self):
        self.brand = BRAND_VISUAL

    def generate(
        self,
        day: str,
        content_summary: str = "",
        platform: str = "nanobana",
        layout: str = "single_image",
        keywords: list = None,
    ) -> dict:
        """
        이미지 프롬프트 생성

        Args:
            day: mon~sun 또는 special_professor
            content_summary: 글 내용 요약 (있으면 맞춤 프롬프트 생성)
            platform: nanobana 또는 grok
            layout: single_image, card_3, card_5
            keywords: 추가 키워드 리스트

        Returns:
            프롬프트 딕셔너리
        """
        style = DAY_VISUAL_STYLES.get(day, DAY_VISUAL_STYLES["mon"])
        plat = PLATFORM_TEMPLATES.get(platform, PLATFORM_TEMPLATES["nanobana"])
        card_layout = CARD_NEWS_LAYOUTS.get(layout, CARD_NEWS_LAYOUTS["single_image"])

        print(f"\n{'='*60}")
        print(f"🎨 이미지 프롬프트 생성")
        print(f"   요일: {day} | 테마: {style['theme']}")
        print(f"   플랫폼: {plat['name']} | 레이아웃: {card_layout['name']}")
        print(f"{'='*60}")

        # 기본 프롬프트 조립
        base_elements = self._select_elements(style, content_summary, keywords)
        
        result = {
            "day": day,
            "theme": style["theme"],
            "platform": platform,
            "layout": layout,
            "brand_colors": self.brand["colors"],
            "prompts": [],
            "generated_at": datetime.now().isoformat(),
        }

        if layout == "single_image":
            prompt = self._build_single_prompt(base_elements, style, plat)
            result["prompts"].append(prompt)
        else:
            # 카드뉴스 (여러 장)
            slides = card_layout.get("slides", [])
            for i, slide in enumerate(slides):
                prompt = self._build_slide_prompt(
                    base_elements, style, plat, slide, i + 1, len(slides)
                )
                result["prompts"].append(prompt)

        # 네거티브 프롬프트
        result["negative_prompt"] = self._build_negative_prompt()

        # 사용 가이드
        result["usage_guide"] = self._build_usage_guide(plat, card_layout)

        return result

    def _select_elements(self, style: dict, content_summary: str, keywords: list = None) -> dict:
        """콘텐츠 기반 핵심 요소 선택"""
        elements = {
            "primary_element": style["elements"][0],
            "secondary_element": style["elements"][1] if len(style["elements"]) > 1 else "",
            "mood": style["mood"],
            "palette": style["palette"],
            "style_keywords": style["style_keywords"],
        }

        # 콘텐츠 요약에서 키워드 추출
        if content_summary:
            content_lower = content_summary.lower()

            # NF 관련 키워드 매핑
            keyword_visual_map = {
                "selumetinib": "glowing medicine capsule",
                "koselugo": "breakthrough medicine with golden light",
                "임상시험": "clinical trial progress chart with hopeful arrows",
                "clinical trial": "clinical trial progress chart with hopeful arrows",
                "수술": "gentle healing hands with soft light",
                "surgery": "gentle healing hands with soft light",
                "유전": "beautiful DNA double helix with warm glow",
                "genetic": "beautiful DNA double helix with warm glow",
                "아이": "happy child playing in sunlit garden",
                "children": "happy child playing in sunlit garden",
                "가족": "loving family together in warm light",
                "family": "loving family together in warm light",
                "환우회": "community circle of diverse people holding hands",
                "community": "community circle of diverse people holding hands",
                "정책": "protective shield with warm government building",
                "policy": "protective shield with warm government building",
                "희망": "sunrise over peaceful landscape with path forward",
                "hope": "sunrise over peaceful landscape with path forward",
            }

            for keyword, visual in keyword_visual_map.items():
                if keyword in content_lower:
                    elements["primary_element"] = visual
                    break

        # 추가 키워드 반영
        if keywords:
            elements["extra_keywords"] = ", ".join(keywords)

        return elements

    def _build_single_prompt(self, elements: dict, style: dict, plat: dict) -> dict:
        """단일 이미지 프롬프트 조립"""
        # 영문 프롬프트 (메인)
        en_prompt = (
            f"{elements['primary_element']}, "
            f"{style['style_keywords']}, "
            f"color palette: {elements['palette']}, "
            f"mood: {elements['mood']}, "
            f"soft natural lighting, "
            f"warm and hopeful atmosphere, "
            f"no text overlay"
        )

        if elements.get("extra_keywords"):
            en_prompt += f", {elements['extra_keywords']}"

        en_prompt = plat["prefix"] + en_prompt + plat["suffix"]

        # 한글 설명
        ko_description = self._generate_ko_description(elements, style)

        return {
            "role": "main",
            "description_ko": ko_description,
            "prompt_en": en_prompt,
            "aspect_ratio": plat["aspect_ratios"]["square"],
            "style_suggestion": style["style_keywords"].split(",")[0].strip(),
        }

    def _build_slide_prompt(
        self, elements: dict, style: dict, plat: dict,
        slide: dict, slide_num: int, total_slides: int
    ) -> dict:
        """카드뉴스 개별 슬라이드 프롬프트"""
        role = slide["role"]
        add = slide["prompt_add"]

        if role == "cover":
            main_element = elements["primary_element"]
        elif role == "closing":
            main_element = "warm community gathering, hands together, hopeful sunset"
        else:
            main_element = elements.get("secondary_element", elements["primary_element"])

        en_prompt = (
            f"{main_element}, "
            f"{add}, "
            f"{style['style_keywords']}, "
            f"color palette: {elements['palette']}, "
            f"mood: {elements['mood']}"
        )
        en_prompt = plat["prefix"] + en_prompt + plat["suffix"]

        return {
            "role": role,
            "slide": f"{slide_num}/{total_slides}",
            "description_ko": f"[{slide_num}번 슬라이드: {role}] {self._role_ko(role)}",
            "prompt_en": en_prompt,
            "aspect_ratio": plat["aspect_ratios"]["card"],
        }

    def _role_ko(self, role: str) -> str:
        """슬라이드 역할 한글 설명"""
        role_map = {
            "cover": "표지 — 시선을 끄는 메인 비주얼, 제목 공간 확보",
            "content": "본문 — 핵심 내용을 시각적으로 전달",
            "key_point_1": "핵심 포인트 1 — 첫 번째 주요 내용 시각화",
            "key_point_2": "핵심 포인트 2 — 데이터/수치 시각화",
            "key_point_3": "핵심 포인트 3 — 사람/감성 요소",
            "closing": "마무리 — 따뜻한 응원, CTA (함께해요) 메시지",
        }
        return role_map.get(role, role)

    def _generate_ko_description(self, elements: dict, style: dict) -> str:
        """이미지 한글 설명 생성"""
        descriptions = {
            "DNA helix with warm glow": "따뜻한 빛으로 감싸인 DNA 이중나선 — 유전 연구의 희망을 상징",
            "microscope with soft light": "부드러운 빛이 비치는 현미경 — 과학적 발견의 설렘",
            "family embracing with warm light": "따뜻한 빛 속에서 서로 안아주는 가족 — 사랑과 지지",
            "parent holding child's hand": "부모가 아이의 손을 잡고 있는 모습 — 함께하는 용기",
            "world map with connected lights": "세계 지도 위의 연결된 빛들 — 글로벌 NF 커뮤니티",
            "pill or medicine with soft glow of hope": "희망의 빛을 내는 약 — 치료제 개발의 진전",
            "protective umbrella over family": "가족을 감싸는 보호 우산 — 정책과 제도의 안전망",
            "person in nature with peaceful expression": "자연 속 평화로운 표정의 사람 — 일상의 소중한 쉼",
            "open journal with highlights": "하이라이트가 가득한 열린 일지 — 한 주의 소중한 기록",
            "glowing medicine capsule": "빛나는 치료제 캡슐 — 셀루메티닙/코셀루고의 희망",
            "breakthrough medicine with golden light": "황금빛에 싸인 신약 — 코셀루고 승인의 기쁜 소식",
            "happy child playing in sunlit garden": "햇살 가득한 정원에서 뛰노는 아이 — 밝은 미래",
            "loving family together in warm light": "따뜻한 빛 속 함께하는 가족 — 사랑의 힘",
            "community circle of diverse people holding hands": "다양한 사람들이 손을 잡은 원 — 환우 커뮤니티의 힘",
            "beautiful DNA double helix with warm glow": "아름답게 빛나는 DNA 이중나선 — 유전학의 진보",
            "sunrise over peaceful landscape with path forward": "평화로운 풍경 위 일출과 앞으로 나아가는 길 — 희망",
        }

        primary = elements.get("primary_element", "")
        return descriptions.get(primary, f"END NF 테마 이미지: {primary}")

    def _build_negative_prompt(self) -> str:
        """네거티브 프롬프트 (피할 요소)"""
        return ", ".join([
            "dark atmosphere",
            "gloomy colors",
            "realistic medical gore",
            "tumors",
            "crying people",
            "hospital equipment",
            "isolated lonely figure",
            "scary imagery",
            "low quality",
            "blurry",
            "text",
            "watermark",
            "deformed",
        ])

    def _build_usage_guide(self, plat: dict, layout: dict) -> dict:
        """플랫폼별 사용 가이드"""
        return {
            "platform": plat["name"],
            "tips": plat["tips"],
            "recommended_ratio": plat["aspect_ratios"].get(
                "card" if layout["count"] > 1 else "square", "1:1"
            ),
            "layout_description": layout["description"],
            "total_images": layout["count"],
        }

    def generate_from_post(self, post_filepath: str, platform: str = "nanobana", layout: str = "single_image") -> dict:
        """기존 포스팅 파일에서 이미지 프롬프트 생성"""
        with open(post_filepath, "r", encoding="utf-8") as f:
            post_data = json.load(f)

        day = post_data.get("day", "mon")
        content = post_data.get("content", "")

        # 콘텐츠 요약 (첫 500자)
        content_summary = content[:500]

        return self.generate(
            day=day,
            content_summary=content_summary,
            platform=platform,
            layout=layout,
        )

    def generate_all_days(self, platform: str = "nanobana", layout: str = "single_image") -> dict:
        """전체 요일 프롬프트 일괄 생성"""
        all_results = {}
        days = ["mon", "tue", "wed", "thu", "fri", "sat", "sun", "special_professor"]

        for day in days:
            result = self.generate(day=day, platform=platform, layout=layout)
            all_results[day] = result

        return all_results

    def save_result(self, result: dict, filename: str = ""):
        """결과 저장"""
        if not filename:
            day = result.get("day", "unknown")
            kst = timezone(timedelta(hours=9))
            date_str = datetime.now(kst).strftime("%Y%m%d")
            filename = f"image_prompts_{day}_{date_str}.json"

        filepath = os.path.join(OUTPUT_DIR, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"💾 저장: {filepath}")

        # 사용하기 쉬운 텍스트 파일도 생성
        txt_filepath = filepath.replace(".json", ".txt")
        with open(txt_filepath, "w", encoding="utf-8") as f:
            f.write(self._format_for_copy(result))
        print(f"📋 복사용 텍스트: {txt_filepath}")

        return filepath

    def _format_for_copy(self, result: dict) -> str:
        """복사해서 바로 쓸 수 있는 텍스트 형식"""
        lines = []
        lines.append(f"🎨 END NF 이미지 프롬프트")
        lines.append(f"테마: {result.get('theme', '')}")
        lines.append(f"플랫폼: {result.get('platform', '')}")
        lines.append(f"생성일: {result.get('generated_at', '')[:10]}")
        lines.append("")

        for i, prompt in enumerate(result.get("prompts", []), 1):
            lines.append(f"{'━'*50}")
            if len(result["prompts"]) > 1:
                lines.append(f"📌 [{prompt.get('slide', f'{i}번')}] {prompt.get('role', '')}")
            lines.append(f"[한글 설명] {prompt.get('description_ko', '')}")
            lines.append(f"")
            lines.append(f"[영문 프롬프트 — 복사용]")
            lines.append(f"{prompt.get('prompt_en', '')}")
            lines.append(f"")
            lines.append(f"비율: {prompt.get('aspect_ratio', '1:1')}")
            lines.append("")

        # 네거티브 프롬프트
        neg = result.get("negative_prompt", "")
        if neg:
            lines.append(f"{'━'*50}")
            lines.append(f"[네거티브 프롬프트 — 복사용]")
            lines.append(neg)
            lines.append("")

        # 사용 가이드
        guide = result.get("usage_guide", {})
        if guide:
            lines.append(f"{'━'*50}")
            lines.append(f"💡 사용 가이드 ({guide.get('platform', '')})")
            for tip in guide.get("tips", []):
                lines.append(f"  → {tip}")

        return "\n".join(lines)


# ============================================================
# CLI 실행
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="END NF 이미지 프롬프트 생성기")
    parser.add_argument("--day", type=str, default="",
                        help="요일 (mon~sun, special_professor, all)")
    parser.add_argument("--platform", type=str, default="nanobana",
                        choices=["nanobana", "grok"],
                        help="이미지 생성 플랫폼")
    parser.add_argument("--style", type=str, default="single_image",
                        choices=["single_image", "card_3", "card_5"],
                        help="레이아웃 스타일")
    parser.add_argument("--input", type=str, default="",
                        help="기존 포스팅 파일 경로")
    parser.add_argument("--preview", action="store_true",
                        help="미리보기만 (저장 안 함)")
    parser.add_argument("--both", action="store_true",
                        help="나노바나나 + 그록 동시 생성")
    args = parser.parse_args()

    generator = ImagePromptGenerator()

    if args.input:
        result = generator.generate_from_post(args.input, args.platform, args.style)
        if not args.preview:
            generator.save_result(result)
    elif args.day == "all":
        platforms = ["nanobana", "grok"] if args.both else [args.platform]
        for plat in platforms:
            results = generator.generate_all_days(plat, args.style)
            if not args.preview:
                kst = timezone(timedelta(hours=9))
                date_str = datetime.now(kst).strftime("%Y%m%d")
                filename = f"image_prompts_all_{plat}_{date_str}.json"
                filepath = os.path.join(OUTPUT_DIR, filename)
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(results, f, ensure_ascii=False, indent=2)
                print(f"💾 전체 저장: {filepath}")
    elif args.day:
        platforms = ["nanobana", "grok"] if args.both else [args.platform]
        for plat in platforms:
            result = generator.generate(day=args.day, platform=plat, layout=args.style)
            if not args.preview:
                generator.save_result(result)

            # 미리보기 출력
            for prompt in result.get("prompts", []):
                print(f"\n📌 {prompt.get('description_ko', '')}")
                print(f"   [{plat}] {prompt.get('prompt_en', '')[:100]}...")
    else:
        print("사용법: python image_prompt_generator.py --day mon")
        print("        python image_prompt_generator.py --day thu --style card_5 --both")


if __name__ == "__main__":
    main()
