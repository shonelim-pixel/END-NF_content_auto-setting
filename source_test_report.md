# END NF 자동 콘텐츠 시스템 - 1단계 소스 테스트 리포트

**작성일**: 2026-03-01  
**상태**: ✅ 1단계 완료

---

## 📊 소스 확보 현황 총괄

| 카테고리 | 소스 수 | API 확인 | 접근 가능 | 비고 |
|---------|---------|---------|---------|------|
| 월: 국제 논문 | 3 | ✅ | ✅ | PubMed E-utilities 정상 |
| 화: 환자 이야기 | 3 | ✅ | ✅ | Reddit JSON API + CTF |
| 수: 해외 커뮤니티 | 6 | ✅ | ✅ | CTF, NF Network 등 |
| 목: 치료제/임상 | 4 | ✅ | ✅ | ClinicalTrials.gov v2 |
| 금: 정책/제도 | 5 | ✅ | ✅ | Google News RSS (한/영) |
| 토: 힐링 콘텐츠 | 3 | ⚠️ | ⚠️ | Instagram API 제한 |
| 일: 주간 하이라이트 | - | - | - | 자동 생성 |
| 특집: 이범희 교수님 | 4 | ✅ | ✅ | PubMed + KoreaMed |

---

## 🔬 소스별 상세 테스트 결과

### 1. PubMed E-utilities API

- **엔드포인트**: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/`
- **인증**: API 키 선택사항 (없으면 3req/sec, 있으면 10req/sec)
- **테스트 결과**: ✅ API 구조 확인, 검색 파라미터 검증 완료
- **NF 관련 논문 현황**: 수천 건 이상 (매월 새 논문 게시)
- **수집기**: `pubmed_fetcher.py` 구현 완료
- **주요 검색어**: neurofibromatosis, NF1, schwannomatosis, selumetinib, MEK inhibitor

### 2. ClinicalTrials.gov API v2

- **엔드포인트**: `https://clinicaltrials.gov/api/v2/studies`
- **인증**: 불필요 (공개 API)
- **테스트 결과**: ✅ REST API JSON 응답 확인
- **NF 관련 임상시험**: 모집 중인 연구 다수 확인
- **수집기**: `clinical_trials_fetcher.py` 구현 완료
- **주요 발견**:
  - Selumetinib(Koselugo) 관련 연구 활발
  - NF2-SWN 관련 INTUITT-NF2 등 새로운 시험 진행 중
  - CTF Drug Pipeline 페이지에 최신 파이프라인 정보 제공

### 3. Google News RSS

- **엔드포인트**: `https://news.google.com/rss/search?q=...`
- **인증**: 불필요
- **테스트 결과**: ✅ 한국어/영어 모두 정상 수집
- **수집기**: `news_fetcher.py` 구현 완료
- **카테고리별 피드**:
  - 커뮤니티 뉴스: 2개 피드
  - 치료제 뉴스: 3개 피드  
  - 한국 정책: 3개 피드
  - 글로벌 정책: 2개 피드

### 4. Reddit r/neurofibromatosis

- **엔드포인트**: `https://www.reddit.com/r/neurofibromatosis/.json`
- **인증**: 기본 JSON API는 인증 불필요
- **테스트 결과**: ✅ 긍정적 게시물 필터링 로직 구현
- **수집기**: `patient_story_fetcher.py` 구현 완료
- **특이사항**: 
  - 부정적 콘텐츠 자동 필터링 적용
  - 긍정도 점수 기반 정렬

### 5. CTF (Children's Tumor Foundation)

- **사이트**: `https://www.ctf.org/`
- **확인된 소스**:
  - Stories of NF: `https://www.ctf.org/storiesofnf/` ✅
  - News: `https://www.ctf.org/news/` ✅
  - Clinical Drug Pipeline: `https://www.ctf.org/clinical-drug-pipeline/` ✅
  - Research Portfolio: `https://www.ctf.org/researchportfolio/` ✅
  - Resource Library: `https://www.ctf.org/resource-library/` ✅
- **최근 주요 뉴스**:
  - Koselugo(selumetinib) 유럽 위원회 정식 승인 (2026.01.14)
  - YIA(Young Investigator Award) 수상자 발표
  - INTUITT-NF2 임상시험 진행 중

### 6. 한국 희귀질환 관련 소스

- **보건복지부**: 정책 뉴스 게시판 확인 ✅
- **한국희귀질환재단(KRDF)**: `https://www.krdf.org/` ✅
- **건강보험심사평가원**: 공고 게시판 확인 ✅
- **Google News 한국어**: 희귀질환/신경섬유종 검색 정상 ✅

### 7. 이범희 교수님 관련 소스

- **PubMed 검색**: "Lee Beom Hee" + genetics/rare disease 검색 가능 ✅
- **KoreaMed**: 한국 의학 논문 검색 가능 ✅
- **서울대병원**: 의료진 정보 및 연구 실적 확인 가능 ✅
- **대한유전학회**: 학술대회/발표 자료 확인 가능 ✅

---

## 📁 산출물 목록

| 파일 | 설명 | 상태 |
|------|------|------|
| `source_config.yaml` | 전체 소스 설정 파일 | ✅ 완료 |
| `pubmed_fetcher.py` | PubMed 논문 수집기 | ✅ 완료 |
| `news_fetcher.py` | 뉴스/RSS 수집기 | ✅ 완료 |
| `clinical_trials_fetcher.py` | 임상시험 수집기 | ✅ 완료 |
| `patient_story_fetcher.py` | 환자 이야기 수집기 | ✅ 완료 |
| `requirements.txt` | Python 의존성 | ✅ 완료 |
| `.github/workflows/daily_collect.yml` | 스케줄링 설정 | ✅ 완료 |
| `source_test_report.md` | 소스 테스트 리포트 (이 문서) | ✅ 완료 |

---

## ⚠️ 주의사항 및 제약사항

1. **Instagram API**: 공식 API 접근에 비즈니스 계정 필요. 현재는 수동 참고용으로 설정
2. **Reddit Rate Limit**: 인증 없이 60req/min. 대량 수집 시 OAuth 앱 등록 권장
3. **웹 스크래핑**: CTF, 보건복지부 등 사이트 구조 변경 시 셀렉터 업데이트 필요
4. **Google Scholar**: 공식 API 미제공. 대안으로 PubMed 집중 활용
5. **NCBI API 키**: 대량 수집 시 무료 API 키 발급 권장 (https://www.ncbi.nlm.nih.gov/account/)

---

## 🔜 다음 단계 (2단계) 예고

**2단계: 자동 수집 크롤러 개발 (2~3일)**
- 수집기들을 통합하는 메인 오케스트레이터 개발
- 요일별 자동 수집 스케줄러 구현
- 데이터 정규화 및 중복 제거 파이프라인
- 에러 핸들링 및 재시도 로직
- 로컬 테스트 환경 구성

---

**✅ 1단계 완료** | 작성: END NF 콘텐츠 봇 | 승인 대기 중
