"""
============================================================
END NF 콘텐츠 시스템 - 환자 이야기 수집기
============================================================
CTF Stories of NF, Reddit, NF Network 등에서 긍정적인 환자 이야기를 수집합니다.

사용법:
    python patient_story_fetcher.py
    python patient_story_fetcher.py --source reddit
    python patient_story_fetcher.py --source ctf
"""

import os
import json
import re
from datetime import datetime
from html import unescape
import argparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    HAS_REQUESTS = False


def http_get(url: str, timeout: int = 30, headers: dict = None) -> str:
    default_headers = {"User-Agent": "ENDNF-ContentBot/1.0 (educational; NF patient support)"}
    if headers:
        default_headers.update(headers)

    if HAS_REQUESTS:
        resp = requests.get(url, timeout=timeout, headers=default_headers)
        resp.raise_for_status()
        return resp.text
    else:
        req = urllib.request.Request(url, headers=default_headers)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")


# ── 긍정적 스토리 필터링 키워드 ──
POSITIVE_KEYWORDS = [
    # 영어
    "hope", "hopeful", "grateful", "thankful", "blessed",
    "milestone", "achievement", "success", "progress",
    "positive", "happy", "joy", "love", "strength", "strong",
    "overcome", "survivor", "warrior", "brave", "courage",
    "support", "community", "together", "inspire", "inspiring",
    "celebrate", "win", "victory", "improve", "better",
    "healing", "recovery", "treatment worked", "good news",
    # 한국어
    "희망", "감사", "극복", "응원", "함께", "사랑", "행복",
    "치료", "회복", "힘", "용기", "긍정", "좋은 소식",
]

NEGATIVE_KEYWORDS = [
    "suicide", "kill myself", "give up", "hopeless", "worthless",
    "자살", "포기", "절망",
]


class PatientStoryFetcher:
    """NF 환자 이야기 수집기"""

    def fetch_reddit(self, max_results: int = 20, time_filter: str = "month") -> list:
        """
        Reddit r/neurofibromatosis에서 긍정적 게시물 수집

        Args:
            max_results: 최대 결과 수
            time_filter: week, month, year, all

        Returns:
            게시물 리스트
        """
        print("=" * 60)
        print("🔵 Reddit r/neurofibromatosis 수집")
        print("=" * 60)

        stories = []

        # Reddit JSON API (인증 없이 접근 가능)
        urls = [
            f"https://www.reddit.com/r/neurofibromatosis/top.json?t={time_filter}&limit={max_results}",
            f"https://www.reddit.com/r/neurofibromatosis/hot.json?limit={max_results}",
        ]

        for url in urls:
            print(f"  📥 수집 중: {url[:60]}...")
            try:
                data = json.loads(http_get(url))
                posts = data.get("data", {}).get("children", [])

                for post in posts:
                    pd = post.get("data", {})
                    title = pd.get("title", "")
                    body = pd.get("selftext", "")
                    score = pd.get("score", 0)
                    created = pd.get("created_utc", 0)
                    permalink = pd.get("permalink", "")
                    num_comments = pd.get("num_comments", 0)

                    # 부정적 콘텐츠 필터링
                    full_text = f"{title} {body}".lower()
                    if any(neg in full_text for neg in NEGATIVE_KEYWORDS):
                        continue

                    # 긍정도 점수 계산
                    positivity = sum(1 for kw in POSITIVE_KEYWORDS if kw.lower() in full_text)

                    stories.append({
                        "source": "reddit",
                        "title": title,
                        "body": body[:1000],
                        "score": score,
                        "positivity_score": positivity,
                        "num_comments": num_comments,
                        "url": f"https://reddit.com{permalink}",
                        "created_at": datetime.fromtimestamp(created).isoformat() if created else "",
                        "fetched_at": datetime.now().isoformat(),
                    })

                print(f"     → {len(posts)}건 수집")

            except Exception as e:
                print(f"     ❌ 수집 실패: {e}")

        # 중복 제거 + 긍정도 순 정렬
        seen_urls = set()
        unique = []
        for story in stories:
            if story["url"] not in seen_urls:
                seen_urls.add(story["url"])
                unique.append(story)

        unique.sort(key=lambda x: (x["positivity_score"], x["score"]), reverse=True)
        print(f"\n✅ Reddit: 총 {len(unique)}건 수집 (긍정도 순 정렬)")
        return unique

    def fetch_ctf_stories(self) -> list:
        """
        CTF Stories of NF 페이지에서 환자 이야기 수집
        (웹 스크래핑 - 구조가 변경될 수 있음)
        """
        print("\n" + "=" * 60)
        print("💙 CTF Stories of NF 수집")
        print("=" * 60)

        stories = []
        url = "https://www.ctf.org/storiesofnf/"

        try:
            html = http_get(url)

            # 간단한 HTML 파싱 (BeautifulSoup 없이)
            # CTF 사이트의 스토리 카드 패턴 매칭
            # 실제 운영 시 BeautifulSoup/Scrapy로 교체 권장

            # <a href="/storiesofnf/..." 패턴 추출
            story_links = re.findall(
                r'href="(/storiesofnf/[^"]+)"[^>]*>',
                html
            )

            # 제목 패턴
            titles = re.findall(
                r'<h[23][^>]*class="[^"]*"[^>]*>([^<]+)</h[23]>',
                html
            )

            print(f"  → 스토리 링크 {len(story_links)}개 발견")
            print(f"  → 제목 {len(titles)}개 발견")

            # 고유 링크만 수집
            seen = set()
            for link in story_links:
                if link not in seen:
                    seen.add(link)
                    stories.append({
                        "source": "ctf_stories",
                        "title": "",
                        "url": f"https://www.ctf.org{link}",
                        "fetched_at": datetime.now().isoformat(),
                        "note": "상세 내용은 개별 페이지 방문 필요",
                    })

            print(f"\n✅ CTF Stories: {len(stories)}건 링크 수집")

        except Exception as e:
            print(f"  ❌ CTF 수집 실패: {e}")

        return stories

    def fetch_ctf_news_stories(self) -> list:
        """CTF 뉴스에서 환자 관련 스토리 수집"""
        print("\n" + "=" * 60)
        print("📰 CTF News - 환자 스토리 필터링")
        print("=" * 60)

        stories = []
        url = "https://www.ctf.org/news/"

        try:
            html = http_get(url)

            # 뉴스 아이템 링크 추출
            news_links = re.findall(
                r'href="(/news/[^"]+)"',
                html
            )

            seen = set()
            for link in news_links:
                if link not in seen and link != "/news/":
                    seen.add(link)
                    stories.append({
                        "source": "ctf_news",
                        "url": f"https://www.ctf.org{link}",
                        "fetched_at": datetime.now().isoformat(),
                    })

            print(f"  → {len(stories)}개 뉴스 링크 수집")

        except Exception as e:
            print(f"  ❌ CTF 뉴스 수집 실패: {e}")

        return stories

    def fetch_healing_content(self) -> list:
        """토요일용 힐링 콘텐츠 소스 수집"""
        print("\n" + "=" * 60)
        print("🌿 힐링 콘텐츠 수집")
        print("=" * 60)

        items = []

        # Reddit에서 힐링/일상 관련 게시물
        healing_keywords = [
            "daily life", "living with", "self care", "exercise",
            "meditation", "art", "creative", "hobby", "nature",
            "healing", "wellness", "mindfulness", "gratitude",
        ]

        try:
            url = "https://www.reddit.com/r/neurofibromatosis/new.json?limit=50"
            data = json.loads(http_get(url))
            posts = data.get("data", {}).get("children", [])

            for post in posts:
                pd = post.get("data", {})
                title = pd.get("title", "").lower()
                body = pd.get("selftext", "").lower()
                full_text = f"{title} {body}"

                # 부정적 콘텐츠 필터링
                if any(neg in full_text for neg in NEGATIVE_KEYWORDS):
                    continue

                # 힐링 관련 키워드 매칭
                healing_score = sum(1 for kw in healing_keywords if kw in full_text)
                if healing_score > 0:
                    items.append({
                        "source": "reddit_healing",
                        "title": pd.get("title", ""),
                        "body": pd.get("selftext", "")[:500],
                        "healing_score": healing_score,
                        "url": f"https://reddit.com{pd.get('permalink', '')}",
                        "fetched_at": datetime.now().isoformat(),
                    })

            items.sort(key=lambda x: x["healing_score"], reverse=True)
            print(f"  → 힐링 게시물 {len(items)}건 수집")

        except Exception as e:
            print(f"  ❌ 힐링 콘텐츠 수집 실패: {e}")

        return items

    def fetch_all(self) -> dict:
        """모든 환자 이야기 소스 수집"""
        return {
            "reddit_stories": self.fetch_reddit(),
            "ctf_stories": self.fetch_ctf_stories(),
            "ctf_news": self.fetch_ctf_news_stories(),
            "healing": self.fetch_healing_content(),
        }


def save_results(data, filename: str):
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 저장 완료: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="END NF 환자 이야기 수집기")
    parser.add_argument("--source", type=str, default="all",
                        help="수집 소스 (reddit, ctf, healing, all)")
    parser.add_argument("--max", type=int, default=20, help="최대 결과 수")
    parser.add_argument("--output", type=str, default="", help="출력 파일명")
    args = parser.parse_args()

    fetcher = PatientStoryFetcher()

    if args.source == "reddit":
        results = fetcher.fetch_reddit(args.max)
    elif args.source == "ctf":
        results = {
            "stories": fetcher.fetch_ctf_stories(),
            "news": fetcher.fetch_ctf_news_stories(),
        }
    elif args.source == "healing":
        results = fetcher.fetch_healing_content()
    else:
        results = fetcher.fetch_all()

    filename = args.output or f"patient_stories_{datetime.now().strftime('%Y%m%d')}.json"
    save_results(results, filename)


if __name__ == "__main__":
    main()
