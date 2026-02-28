"""
============================================================
END NF 콘텐츠 시스템 - PubMed 논문 수집기
============================================================
PubMed E-utilities API를 사용하여 NF 관련 최신 논문을 수집합니다.

사용법:
    python pubmed_fetcher.py
    python pubmed_fetcher.py --days 7 --max 20
    python pubmed_fetcher.py --query "selumetinib NF1" --output results.json

환경변수:
    NCBI_API_KEY: NCBI API 키 (선택사항, 없으면 3req/sec 제한)
"""

import os
import json
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from urllib.parse import quote
from typing import Optional
import argparse

# ── 직접 HTTP 요청 (requests 없이도 동작) ──
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    import urllib.request
    import urllib.error
    HAS_REQUESTS = False


def http_get(url: str, timeout: int = 30) -> str:
    """HTTP GET 요청 (requests 또는 urllib 사용)"""
    if HAS_REQUESTS:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    else:
        req = urllib.request.Request(url, headers={"User-Agent": "ENDNF-ContentBot/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8")


# ── 설정 ──
BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
API_KEY = os.environ.get("NCBI_API_KEY", "")

DEFAULT_QUERIES = [
    "neurofibromatosis",
    "neurofibromatosis type 1 treatment",
    "NF1 plexiform neurofibroma",
    "selumetinib neurofibromatosis",
    "schwannomatosis therapy",
    "MEK inhibitor NF1",
    "neurofibromatosis gene therapy",
]

PROFESSOR_LEE_QUERIES = [
    "Lee Beom Hee[Author] AND genetics",
    "Lee BH[Author] AND Seoul National University AND rare disease",
    "Lee Beom Hee[Author] AND neurofibromatosis",
]


class PubMedFetcher:
    """PubMed E-utilities를 통한 NF 논문 수집기"""

    def __init__(self, api_key: str = ""):
        self.api_key = api_key or API_KEY
        self.delay = 0.1 if self.api_key else 0.34  # API키 있으면 10req/s, 없으면 3req/s

    def _build_params(self, params: dict) -> str:
        """URL 파라미터 빌드"""
        if self.api_key:
            params["api_key"] = self.api_key
        params["tool"] = "ENDNF_ContentBot"
        params["email"] = "endnf.content@gmail.com"
        return "&".join(f"{k}={quote(str(v))}" for k, v in params.items())

    def search(self, query: str, max_results: int = 10, days_back: int = 30) -> list:
        """
        PubMed 검색 후 PMID 리스트 반환

        Args:
            query: 검색어
            max_results: 최대 결과 수
            days_back: 최근 N일 이내 논문만

        Returns:
            PMID 문자열 리스트
        """
        date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")
        date_to = datetime.now().strftime("%Y/%m/%d")

        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "sort": "date",
            "datetype": "pdat",
            "mindate": date_from,
            "maxdate": date_to,
            "retmode": "json",
        }

        url = f"{BASE_URL}/esearch.fcgi?{self._build_params(params)}"
        print(f"  🔍 검색: '{query}' (최근 {days_back}일)")

        try:
            data = json.loads(http_get(url))
            id_list = data.get("esearchresult", {}).get("idlist", [])
            count = data.get("esearchresult", {}).get("count", "0")
            print(f"     → 총 {count}건 중 {len(id_list)}건 수집")
            time.sleep(self.delay)
            return id_list
        except Exception as e:
            print(f"     ❌ 검색 실패: {e}")
            return []

    def fetch_details(self, pmids: list) -> list:
        """
        PMID 리스트로 논문 상세정보 조회

        Args:
            pmids: PMID 리스트

        Returns:
            논문 상세정보 딕셔너리 리스트
        """
        if not pmids:
            return []

        params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
            "rettype": "abstract",
        }

        url = f"{BASE_URL}/efetch.fcgi?{self._build_params(params)}"
        print(f"  📄 {len(pmids)}건 상세정보 조회 중...")

        try:
            xml_text = http_get(url)
            time.sleep(self.delay)
            return self._parse_articles(xml_text)
        except Exception as e:
            print(f"     ❌ 상세정보 조회 실패: {e}")
            return []

    def _parse_articles(self, xml_text: str) -> list:
        """XML 파싱하여 논문 정보 추출"""
        articles = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            print(f"     ❌ XML 파싱 실패: {e}")
            return []

        for article in root.findall(".//PubmedArticle"):
            try:
                medline = article.find(".//MedlineCitation")
                art = medline.find(".//Article")

                # PMID
                pmid = medline.findtext(".//PMID", "")

                # 제목
                title = art.findtext(".//ArticleTitle", "제목 없음")

                # 초록
                abstract_parts = []
                for abs_text in art.findall(".//Abstract/AbstractText"):
                    label = abs_text.get("Label", "")
                    text = abs_text.text or ""
                    # 태그 내부 텍스트 포함
                    full_text = ET.tostring(abs_text, encoding="unicode", method="text").strip()
                    if label:
                        abstract_parts.append(f"[{label}] {full_text}")
                    else:
                        abstract_parts.append(full_text)
                abstract = " ".join(abstract_parts) if abstract_parts else "초록 없음"

                # 저자
                authors = []
                for author in art.findall(".//AuthorList/Author"):
                    last = author.findtext("LastName", "")
                    first = author.findtext("ForeName", "")
                    if last:
                        authors.append(f"{last} {first}".strip())

                # 저널
                journal = art.findtext(".//Journal/Title", "")
                journal_abbrev = art.findtext(".//Journal/ISOAbbreviation", "")

                # 출판일
                pub_date_elem = art.find(".//Journal/JournalIssue/PubDate")
                if pub_date_elem is not None:
                    year = pub_date_elem.findtext("Year", "")
                    month = pub_date_elem.findtext("Month", "")
                    day = pub_date_elem.findtext("Day", "")
                    pub_date = f"{year} {month} {day}".strip()
                else:
                    pub_date = ""

                # DOI
                doi = ""
                for eid in article.findall(".//PubmedData/ArticleIdList/ArticleId"):
                    if eid.get("IdType") == "doi":
                        doi = eid.text or ""
                        break

                # 키워드
                keywords = []
                for kw in medline.findall(".//KeywordList/Keyword"):
                    if kw.text:
                        keywords.append(kw.text)

                # MeSH 용어
                mesh_terms = []
                for mesh in medline.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
                    if mesh.text:
                        mesh_terms.append(mesh.text)

                articles.append({
                    "pmid": pmid,
                    "title": title,
                    "abstract": abstract[:1000],  # 길이 제한
                    "authors": authors[:5],  # 처음 5명
                    "author_count": len(authors),
                    "journal": journal,
                    "journal_abbrev": journal_abbrev,
                    "pub_date": pub_date,
                    "doi": doi,
                    "keywords": keywords[:10],
                    "mesh_terms": mesh_terms[:10],
                    "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                    "fetched_at": datetime.now().isoformat(),
                })

            except Exception as e:
                print(f"     ⚠️ 논문 파싱 오류: {e}")
                continue

        print(f"     ✅ {len(articles)}건 파싱 완료")
        return articles

    def search_and_fetch(self, query: str, max_results: int = 10, days_back: int = 30) -> list:
        """검색 + 상세정보 조회를 한 번에"""
        pmids = self.search(query, max_results, days_back)
        if not pmids:
            return []
        return self.fetch_details(pmids)

    def fetch_nf_latest(self, days_back: int = 30, max_per_query: int = 5) -> dict:
        """
        모든 NF 관련 쿼리로 최신 논문 수집

        Returns:
            {query: [articles]} 딕셔너리
        """
        print("=" * 60)
        print("📚 PubMed NF 최신 논문 수집 시작")
        print(f"   기간: 최근 {days_back}일")
        print("=" * 60)

        results = {}
        seen_pmids = set()

        for query in DEFAULT_QUERIES:
            articles = self.search_and_fetch(query, max_per_query, days_back)
            # 중복 제거
            unique = []
            for art in articles:
                if art["pmid"] not in seen_pmids:
                    seen_pmids.add(art["pmid"])
                    unique.append(art)
            results[query] = unique
            print(f"     (고유 논문: {len(unique)}건)")
            print()

        total = sum(len(v) for v in results.values())
        print(f"✅ 총 {total}건의 고유 논문 수집 완료")
        return results

    def fetch_professor_lee(self, days_back: int = 365) -> list:
        """이범희 교수님 관련 논문 수집"""
        print("\n" + "=" * 60)
        print("🏥 이범희 교수님 관련 논문 수집")
        print("=" * 60)

        all_articles = []
        seen_pmids = set()

        for query in PROFESSOR_LEE_QUERIES:
            articles = self.search_and_fetch(query, 10, days_back)
            for art in articles:
                if art["pmid"] not in seen_pmids:
                    seen_pmids.add(art["pmid"])
                    all_articles.append(art)
            print()

        print(f"✅ 이범희 교수님 관련 {len(all_articles)}건 수집 완료")
        return all_articles


def save_results(data: dict | list, filename: str):
    """결과를 JSON 파일로 저장"""
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)

    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 저장 완료: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="END NF PubMed 논문 수집기")
    parser.add_argument("--days", type=int, default=30, help="최근 N일 이내 (기본: 30)")
    parser.add_argument("--max", type=int, default=5, help="쿼리당 최대 결과 수 (기본: 5)")
    parser.add_argument("--query", type=str, default="", help="특정 검색어 (미지정시 전체 검색)")
    parser.add_argument("--professor", action="store_true", help="이범희 교수님 논문 수집")
    parser.add_argument("--output", type=str, default="", help="출력 파일명")
    args = parser.parse_args()

    fetcher = PubMedFetcher()

    if args.professor:
        results = fetcher.fetch_professor_lee(args.days)
        filename = args.output or f"professor_lee_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)

    elif args.query:
        results = fetcher.search_and_fetch(args.query, args.max, args.days)
        filename = args.output or f"pubmed_custom_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)

    else:
        results = fetcher.fetch_nf_latest(args.days, args.max)
        filename = args.output or f"pubmed_nf_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)


if __name__ == "__main__":
    main()
