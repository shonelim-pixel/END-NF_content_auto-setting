"""
============================================================
END NF 콘텐츠 시스템 - 임상시험 수집기
============================================================
ClinicalTrials.gov API v2를 사용하여 NF 관련 임상시험 정보를 수집합니다.

사용법:
    python clinical_trials_fetcher.py
    python clinical_trials_fetcher.py --status RECRUITING
    python clinical_trials_fetcher.py --query "selumetinib"
"""

import os
import json
from datetime import datetime
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


BASE_URL = "https://clinicaltrials.gov/api/v2/studies"

DEFAULT_QUERIES = [
    "neurofibromatosis",
    "NF1 plexiform neurofibroma",
    "schwannomatosis",
    "neurofibromatosis type 2",
]


class ClinicalTrialsFetcher:
    """ClinicalTrials.gov API v2 임상시험 수집기"""

    def search(
        self,
        query: str = "neurofibromatosis",
        status: list = None,
        max_results: int = 20,
        sort: str = "LastUpdatePostDate",
    ) -> list:
        """
        임상시험 검색

        Args:
            query: 검색어
            status: 상태 필터 (RECRUITING, ACTIVE_NOT_RECRUITING 등)
            max_results: 최대 결과 수
            sort: 정렬 기준

        Returns:
            임상시험 정보 리스트
        """
        if status is None:
            status = ["RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING"]

        print(f"  🔬 임상시험 검색: '{query}'")
        print(f"     상태: {', '.join(status)}")

        # API v2 파라미터
        params = [
            f"query.term={query}",
            f"pageSize={max_results}",
            f"sort={sort}",
        ]

        # 상태 필터
        for s in status:
            params.append(f"filter.overallStatus={s}")

        # 필요한 필드만 요청
        fields = [
            "NCTId", "BriefTitle", "OfficialTitle",
            "OverallStatus", "StartDate", "CompletionDate",
            "BriefSummary", "Condition", "InterventionName",
            "LeadSponsorName", "Phase", "EnrollmentCount",
            "StudyType", "LocationCity", "LocationCountry",
            "LastUpdatePostDate",
        ]

        url = f"{BASE_URL}?{'&'.join(params)}"
        print(f"     URL: {url[:100]}...")

        try:
            data = json.loads(http_get(url))
            studies = data.get("studies", [])
            total = data.get("totalCount", 0)
            print(f"     → 총 {total}건 중 {len(studies)}건 수집")
            return self._parse_studies(studies)
        except Exception as e:
            print(f"     ❌ 검색 실패: {e}")
            return []

    def _parse_studies(self, studies: list) -> list:
        """API 응답 파싱"""
        parsed = []
        for study in studies:
            try:
                protocol = study.get("protocolSection", {})
                ident = protocol.get("identificationModule", {})
                status_mod = protocol.get("statusModule", {})
                desc = protocol.get("descriptionModule", {})
                cond_mod = protocol.get("conditionsModule", {})
                interv_mod = protocol.get("armsInterventionsModule", {})
                sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
                design_mod = protocol.get("designModule", {})
                enroll_mod = design_mod.get("enrollmentInfo", {})
                contact_mod = protocol.get("contactsLocationsModule", {})

                # 치료 방법
                interventions = []
                if interv_mod:
                    for interv in interv_mod.get("interventions", []):
                        interventions.append({
                            "name": interv.get("name", ""),
                            "type": interv.get("type", ""),
                            "description": interv.get("description", "")[:200],
                        })

                # 연구 장소
                locations = []
                if contact_mod:
                    for loc in contact_mod.get("locations", [])[:5]:
                        locations.append({
                            "facility": loc.get("facility", ""),
                            "city": loc.get("city", ""),
                            "country": loc.get("country", ""),
                        })

                nct_id = ident.get("nctId", "")
                parsed.append({
                    "nct_id": nct_id,
                    "title": ident.get("briefTitle", ""),
                    "official_title": ident.get("officialTitle", ""),
                    "status": status_mod.get("overallStatus", ""),
                    "phase": design_mod.get("phases", []),
                    "study_type": design_mod.get("studyType", ""),
                    "start_date": status_mod.get("startDateStruct", {}).get("date", ""),
                    "completion_date": status_mod.get("completionDateStruct", {}).get("date", ""),
                    "last_update": status_mod.get("lastUpdatePostDateStruct", {}).get("date", ""),
                    "brief_summary": desc.get("briefSummary", "")[:500],
                    "conditions": cond_mod.get("conditions", []),
                    "interventions": interventions,
                    "sponsor": sponsor_mod.get("leadSponsor", {}).get("name", ""),
                    "enrollment": enroll_mod.get("count", 0),
                    "locations": locations,
                    "url": f"https://clinicaltrials.gov/study/{nct_id}",
                    "fetched_at": datetime.now().isoformat(),
                })
            except Exception as e:
                print(f"     ⚠️ 파싱 오류: {e}")
                continue

        return parsed

    def fetch_all_nf(self, max_per_query: int = 10) -> dict:
        """모든 NF 관련 쿼리로 임상시험 수집"""
        print("=" * 60)
        print("🔬 ClinicalTrials.gov NF 임상시험 수집")
        print("=" * 60)

        results = {}
        seen_ncts = set()

        for query in DEFAULT_QUERIES:
            trials = self.search(query, max_results=max_per_query)
            unique = []
            for trial in trials:
                if trial["nct_id"] not in seen_ncts:
                    seen_ncts.add(trial["nct_id"])
                    unique.append(trial)
            results[query] = unique
            print(f"     (고유: {len(unique)}건)\n")

        total = sum(len(v) for v in results.values())
        print(f"✅ 총 {total}건의 고유 임상시험 수집 완료")
        return results

    def fetch_recruiting_only(self, max_results: int = 20) -> list:
        """모집 중인 NF 임상시험만 수집"""
        return self.search(
            "neurofibromatosis",
            status=["RECRUITING"],
            max_results=max_results,
        )


def save_results(data, filename: str):
    output_dir = os.path.join(os.path.dirname(__file__), "data")
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"💾 저장 완료: {filepath}")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="END NF 임상시험 수집기")
    parser.add_argument("--query", type=str, default="", help="검색어")
    parser.add_argument("--status", type=str, default="RECRUITING",
                        help="상태 필터 (RECRUITING, ACTIVE_NOT_RECRUITING 등)")
    parser.add_argument("--max", type=int, default=20, help="최대 결과 수")
    parser.add_argument("--output", type=str, default="", help="출력 파일명")
    args = parser.parse_args()

    fetcher = ClinicalTrialsFetcher()

    if args.query:
        results = fetcher.search(args.query, [args.status], args.max)
        filename = args.output or f"trials_custom_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)
    else:
        results = fetcher.fetch_all_nf(args.max)
        filename = args.output or f"trials_nf_{datetime.now().strftime('%Y%m%d')}.json"
        save_results(results, filename)


if __name__ == "__main__":
    main()
