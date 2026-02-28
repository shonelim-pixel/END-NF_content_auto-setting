"""
============================================================
END NF 콘텐츠 시스템 - 뉴스/RSS 수집기
============================================================
Google News RSS, NORD, CTF 등에서 NF 관련 뉴스를 수집합니다.

사용법:
    python news_fetcher.py
    python news_fetcher.py --category treatment
    python news_fetcher.py --category policy_kr
"""

import os
import json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from html import unescape
import re
import argparse

try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    HAS_REQUESTS = False


def http_get(url: str, timeout: int = 30) -> str:
    if HAS_REQUESTS:
        resp = requests.get(url, timeout=timeout, headers={"User-Agent": "ENDNF-ContentBot/1.0"})
        resp.raise_for_status()
        return resp.text
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "ENDNF-ContentBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")


# ── RSS 피드 소스 정의 ──
RSS_FEEDS = {
    # ⭐ 핵심 참고처: 레어노트 + CTF
    "rarenote": [
        {
            "name": "레어노트 뉴스",
            "url": "https://rarenote.io/news",
            "lang": "ko",
            "type": "scrape",
        },
    ],

    "ctf": [
        {
            "name": "CTF News",
            "url": "https://www.ctf.org/news/",
            "lang": "en",
            "type": "scrape",
        },
        {
            "name": "CTF Drug Pipeline",
            "url": "https://www.ctf.org/clinical-drug-pipeline/",
            "lang": "en",
            "type": "scrape",
        },
    ],

    # 수요일: 해외 커뮤니티
    "community": [
        {
            "name": "Google News - NF Community",
            "url": "https://news.google.com/rss/search?q=neurofibromatosis+community+foundation&hl=en&gl=US&ceid=US:en",
            "lang": "en",
        },
        {
            "name": "Google News - NF Awareness",
            "url": "https://news.google.com/rss/search?q=neurofibromatosis+awareness+event&hl=en&gl=US&ceid=US:en",
            "lang": "en",
        },
    ],

    # 목요일: 치료제/임상
    "treatment": [
        {
            "name": "Google News - NF Treatment",
            "url": "https://news.google.com/rss/search?q=neurofibromatosis+treatment+drug+2025+OR+2026&hl=en&gl=US&ceid=US:en",
            "lang": "en",
        },
        {
            "name": "Google News - Selumetinib/Koselugo",
            "url": "https://news.google.com/rss/search?q=selumetinib+OR+koselugo+neurofibromatosis&hl=en&gl=US&ceid=US:en",
            "lang": "en",
        },
        {
            "name": "Google News - NF Clinical Trial",
            "url": "https://news.google.com/rss/search?q=neurofibromatosis+clinical+trial&hl=en&gl=US&ceid=US:en",
            "lang": "en",
        },
    ],

    # 금요일: 정책/제도 (한국)
    "policy_kr": [
        {
            "name": "Google News - 희귀질환 정책",
            "url": "https://news.google.com/rss/search?q=%ED%9D%AC%EA%B7%80%EC%A7%88%ED%99%98+%EC%A0%95%EC%B1%85&hl=ko&gl=KR&ceid=KR:ko",
            "lang": "ko",
        },
        {
            "name": "Google News - 신경섬유종",
            "url": "https://news.google.com/rss/search?q=%EC%8B%A0%EA%B2%BD%EC%84%AC%EC%9C%A0%EC%A2%85&hl=ko&gl=KR&ceid=KR:ko",
            "lang": "ko",
        },
        {
            "name": "Google News - 희귀질환 건강보험",
            "url": "https://news.google.com/rss/search?q=%ED%9D%AC%EA%B7%80%EC%A7%88%ED%99%98+%EA%B1%B4%EA%B0%95%EB%B3%B4%ED%97%98&hl=ko&gl=KR&ceid=KR:ko",
            "lang": "ko",
        },
    ],

    # 금요일: 정책/제도 (글로벌)
    "policy_global": [
        {
            "name": "Google News - Rare Disease Policy",
            "url": "https://news.google.com/rss/search?q=rare+disease+policy+regulation+2025+OR+2026&hl=en&gl=US&ceid=US:en",
            "lang": "en",
        },
        {
            "name": "Google News - Orphan Drug",
            "url": "https://news.google.com/rss/search?q=orphan+drug+neurofibromatosis&hl=en&gl=US&ceid=US:en",
            "lang": "en",
        },
    ],

    # 일반 NF 뉴스
    "general": [
        {
            "name": "Google News - Neurofibromatosis",
            "url": "https://news.google.com/rss/search?q=neurofibromatosis&hl=en&gl=US&ceid=US:en",
            "lang": "en",
        },
    ],
}


class NewsFetcher:
    """뉴스/RSS 피드 수집기"""

    def __init__(self):
        self.collected = []

    def scrape_page(self, url: str, source_name: str, lang: str = "ko", max_items: int = 10) -> list:
        """
        웹페이지 스크래핑 (레어노트, CTF 등)

        Args:
            url: 페이지 URL
            source_name: 소스 이름
            lang: 언어
            max_items: 최대 아이템 수

        Returns:
            뉴스 아이템 리스트
        """
        print(f"  🌐 스크래핑: {source_name}")

        try:
            html = http_get(url)
        except Exception as e:
            print(f"     ❌ 스크래핑 실패: {e}")
            return []

        items = []

        # 링크 + 제목 패턴 추출
        # <a href="..." ...>제목</a> 또는 <h2/h3>제목</h2/h3>
        link_patterns = re.findall(
            r'<a[^>]+href="([^"]*)"[^>]*>([^<]{5,100})</a>',
            html
        )

        # 레어노트 특화: /contents/, /news/ 경로
        if "rarenote" in url:
            for href, title in link_patterns:
                if any(path in href for path in ["/contents/", "/news/"]):
                    full_url = href if href.startswith("http") else f"https://rarenote.io{href}"
                    clean_title = self._clean_html(title)
                    if len(clean_title) > 5:
                        items.append({
                            "title": clean_title,
                            "link": full_url,
                            "description": "",
                            "pub_date": "",
                            "source_name": source_name,
                            "language": lang,
                            "category": "rarenote",
                            "fetched_at": datetime.now().isoformat(),
                        })

        # CTF 특화: /news/, /storiesofnf/, /clinical-drug-pipeline/
        elif "ctf.org" in url:
            for href, title in link_patterns:
                if any(path in href for path in ["/news/", "/storiesofnf/", "/clinical-drug-pipeline/"]):
                    full_url = href if href.startswith("http") else f"https://www.ctf.org{href}"
                    clean_title = self._clean_html(title)
                    if len(clean_title) > 5:
                        items.append({
                            "title": clean_title,
                            "link": full_url,
                            "description": "",
                            "pub_date": "",
                            "source_name": source_name,
                            "language": lang,
                            "category": "ctf",
                            "fetched_at": datetime.now().isoformat(),
                        })

        # 일반 스크래핑
        else:
            for href, title in link_patterns[:max_items]:
                full_url = href if href.startswith("http") else f"{url.rstrip('/')}/{href.lstrip('/')}"
                clean_title = self._clean_html(title)
                if len(clean_title) > 5:
                    items.append({
                        "title": clean_title,
                        "link": full_url,
                        "description": "",
                        "pub_date": "",
                        "source_name": source_name,
                        "language": lang,
                        "fetched_at": datetime.now().isoformat(),
                    })

        items = items[:max_items]
        print(f"     → {len(items)}건 수집")
        return items

    def fetch_rss(self, url: str, source_name: str, lang: str = "en", max_items: int = 10) -> list:
        """
        RSS 피드 파싱

        Args:
            url: RSS 피드 URL
            source_name: 소스 이름
            lang: 언어 코드
            max_items: 최대 아이템 수

        Returns:
            뉴스 아이템 리스트
        """
        print(f"  📰 수집: {source_name}")

        try:
            xml_text = http_get(url)
        except Exception as e:
            print(f"     ❌ 수집 실패: {e}")
            return []

        items = []
        try:
            root = ET.fromstring(xml_text)

            # RSS 2.0 형식
            for item in root.findall(".//item")[:max_items]:
                title = item.findtext("title", "")
                link = item.findtext("link", "")
                description = item.findtext("description", "")
                pub_date = item.findtext("pubDate", "")
                source_tag = item.findtext("source", "")

                # HTML 태그 제거 + unescape
                title = self._clean_html(title)
                description = self._clean_html(description)

                items.append({
                    "title": title,
                    "link": link,
                    "description": description[:500],
                    "pub_date": pub_date,
                    "source_name": source_name,
                    "original_source": source_tag,
                    "language": lang,
                    "fetched_at": datetime.now().isoformat(),
                })

            # Atom 형식 (대체)
            if not items:
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                for entry in root.findall(".//atom:entry", ns)[:max_items]:
                    title = entry.findtext("atom:title", "", ns)
                    link_elem = entry.find("atom:link", ns)
                    link = link_elem.get("href", "") if link_elem is not None else ""
                    summary = entry.findtext("atom:summary", "", ns)
                    updated = entry.findtext("atom:updated", "", ns)

                    items.append({
                        "title": self._clean_html(title),
                        "link": link,
                        "description": self._clean_html(summary)[:500],
                        "pub_date": updated,
                        "source_name": source_name,
                        "language": lang,
                        "fetched_at": datetime.now().isoformat(),
                    })

        except ET.ParseError as e:
            print(f"     ❌ XML 파싱 실패: {e}")
            return []

        print(f"     → {len(items)}건 수집")
        return items

    def _clean_html(self, text: str) -> str:
        """HTML 태그 제거 및 텍스트 정리"""
        if not text:
            return ""
        text = unescape(text)
        text = re.sub(r"<[^>]+>", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def fetch_category(self, category: str, max_per_feed: int = 10) -> list:
        """
        특정 카테고리의 모든 RSS 피드 수집

        Args:
            category: RSS_FEEDS 키 (community, treatment, policy_kr 등)
            max_per_feed: 피드당 최대 아이템 수

        Returns:
            뉴스 아이템 리스트
        """
        feeds = RSS_FEEDS.get(category, [])
        if not feeds:
            print(f"⚠️ 알 수 없는 카테고리: {category}")
            print(f"   사용 가능: {', '.join(RSS_FEEDS.keys())}")
            return []

        print(f"\n{'='*60}")
        print(f"📰 [{category.upper()}] 뉴스 수집 시작")
        print(f"   피드 수: {len(feeds)}")
        print(f"{'='*60}")

        all_items = []
        seen_links = set()

        for feed in feeds:
            feed_type = feed.get("type", "rss")

            if feed_type == "scrape":
                items = self.scrape_page(
                    url=feed["url"],
                    source_name=feed["name"],
                    lang=feed.get("lang", "en"),
                    max_items=max_per_feed,
                )
            else:
                items = self.fetch_rss(
                    url=feed["url"],
                    source_name=feed["name"],
                    lang=feed.get("lang", "en"),
                    max_items=max_per_feed,
                )

            # 중복 링크 제거
            for item in items:
                if item["link"] not in seen_links:
                    seen_links.add(item["link"])
                    item["category"] = category
                    all_items.append(item)

        print(f"\n✅ [{category}] 총 {len(all_items)}건 수집 완료 (중복 제거)")
        return all_items

    def fetch_all(self, max_per_feed: int = 10) -> dict:
        """모든 카테고리 수집"""
        results = {}
        for category in RSS_FEEDS:
            results[category] = self.fetch_category(category, max_per_feed)
        return results

    def fetch_by_day(self, day_of_week: str, max_per_feed: int = 10) -> list:
        """
        요일에 맞는 뉴스 수집

        Args:
            day_of_week: mon, tue, wed, thu, fri, sat, sun

        Returns:
            뉴스 아이템 리스트
        """
        day_category_map = {
            "mon": ["general", "rarenote", "ctf"],    # 월: NF 뉴스 + 핵심 참고처
            "tue": ["rarenote"],                       # 화: 환자 이야기 (+ 별도 수집기)
            "wed": ["community", "ctf"],               # 수: 해외 커뮤니티 + CTF
            "thu": ["treatment", "ctf"],               # 목: 치료제/임상 + CTF Pipeline
            "fri": ["policy_kr", "policy_global", "rarenote"],  # 금: 정책 + 레어노트
            "sat": ["rarenote"],                        # 토: 힐링 (+ 별도 수집기)
            "sun": [],                                  # 일: 주간 하이라이트 (자동생성)
        }

        categories = day_category_map.get(day_of_week.lower(), [])
        if not categories:
            print(f"ℹ️ {day_of_week}에는 뉴스 수집 대상이 없습니다.")
            return []

        all_items = []
        for cat in categories:
            all_items.extend(self.fetch_category(cat, max_per_feed))

        return all_items


def save_results(data, filename: str):
    """결과를 JSON 파일로 저장"""
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 저장 완료: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="END NF 뉴스/RSS 수집기")
    parser.add_argument("--category", type=str, default="",
                        help="수집 카테고리 (community, treatment, policy_kr, policy_global, general)")
    parser.add_argument("--day", type=str, default="",
                        help="요일별 수집 (mon, tue, wed, thu, fri, sat, sun)")
    parser.add_argument("--all", action="store_true", help="전체 카테고리 수집")
    parser.add_argument("--max", type=int, default=10, help="피드당 최대 아이템 수")
    parser.add_argument("--output", type=str, default="", help="출력 파일명")
    args = parser.parse_args()

    fetcher = NewsFetcher()

    if args.all:
        results = fetcher.fetch_all(args.max)
        filename = args.output or f"news_all_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)

    elif args.day:
        results = fetcher.fetch_by_day(args.day, args.max)
        filename = args.output or f"news_{args.day}_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)

    elif args.category:
        results = fetcher.fetch_category(args.category, args.max)
        filename = args.output or f"news_{args.category}_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)

    else:
        # 오늘 요일에 맞게 자동 수집
        day_map = {0: "mon", 1: "tue", 2: "wed", 3: "thu", 4: "fri", 5: "sat", 6: "sun"}
        today = day_map[datetime.now().weekday()]
        print(f"📅 오늘은 {today.upper()}요일입니다. 해당 카테고리 뉴스를 수집합니다.")
        results = fetcher.fetch_by_day(today, args.max)
        filename = args.output or f"news_{today}_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)


if __name__ == "__main__":
    main()
