# 대학기관평가인증 편람 비교·검토 대시보드 (3주기 ↔ 4주기)

3주기 대학기관평가인증 편람과 4주기 대학기관평가인증 편람을 **준거(criterion) 단위로 비교/분석**하고, 변경사항 검토(확정/보류/반려), 부서 배정, 증빙자료 관리, 그리고 **로컬 LLM(LM Studio) 기반 AI 질의(RAG)** 를 제공하는 Flask 대시보드입니다.

- Backend: **Python / Flask**
- DB: **SQLite** (`accreditation_review.db`)
- Frontend: **HTML + Vanilla JS + CSS**
- Graph: **vis.js** 기반 지식그래프 시각화
- AI: `openai` SDK를 사용해 **LM Studio(OpenAI-compatible) 로컬 API** 연동

---

## 1) 빠른 시작 (Run)

### 1. 준비물
- Python 3.x
- (선택) LM Studio 실행 및 Local Server 활성화
  - 기본 주소: `http://localhost:1234/v1`

### 2. 설치

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 실행

> ⚠️ 이 프로젝트는 Streamlit이 아니라 **Flask** 입니다.

```bash
python app.py
```

실행 후:
- http://localhost:5000 접속

---

## 2) 환경변수 (AI 연동)

`ai_service.py`에서 다음 환경변수를 사용합니다.

- `AI_BASE_URL` (기본값: `http://localhost:1234/v1`)
- `AI_API_KEY` (기본값: `lm-studio`)
- `AI_MODEL` (기본값: `gemma-2-9b-it`)

예시:

```bash
export AI_BASE_URL="http://localhost:1234/v1"
export AI_API_KEY="lm-studio"
export AI_MODEL="gemma-2-9b-it"
```

Windows PowerShell 예시:

```powershell
$env:AI_BASE_URL="http://localhost:1234/v1"
$env:AI_API_KEY="lm-studio"
$env:AI_MODEL="gemma-2-9b-it"
```

---

## 3) 주요 페이지 & 라우트

| 기능 | URL | 템플릿 |
|---|---|---|
| 현황 대시보드 | `/` | `templates/dashboard.html` |
| 상세 검토 뷰 | `/review` | `templates/review.html` |
| 전체 비교(Full View) | `/fullview` | `templates/fullview.html` |
| 증빙자료 관리 | `/evidence` | `templates/evidence.html` |
| 지식그래프 | `/graph` | `templates/graph.html` |

---

## 4) 핵심 API 엔드포인트(요약)

### 통계/현황
- `GET /api/overview` : 전체 통계(변경 수, 상태별 카운트 등)
- `GET /api/criteria-progress` : 준거별 진행률 (`v_criterion_review_progress`)
- `GET /api/section-stats` : 섹션별 통계 (`v_section_change_stats`)
- `GET /api/department-workload` : 부서별 업무량 (`v_department_workload`)
- `GET /api/mapping-overview` : 3↔4주기 준거 매핑 현황 (`v_mapping_overview`)
- `GET /api/risk-heatmap` : 준거×섹션 위험도 히트맵 데이터

### 변경사항 조회
- `GET /api/criteria-list` : 준거 목록
- `GET /api/changes?criterion=&section=&change_type=&status=` : 변경사항 필터 목록
- `GET /api/change/<change_id>` : 변경사항 상세 + 매칭 후보 + 부서 조치사항

### 검토 워크플로우
- `PATCH /api/change/<change_id>/status` : 검토 상태 업데이트
  - `status`: `confirmed | needs_review | rejected | deferred`
  - `note`, `reviewer` 지원
- `POST /api/change/<change_id>/note` : 검토 메모 추가
- `GET /api/change/<change_id>/history` : 검토 이력 조회 (`review_log`)

### 부서 배정
- `GET /api/departments` : 부서 마스터 목록
- `POST /api/departments` : 부서 추가
- `GET /api/change/<change_id>/departments` : 변경사항에 배정된 부서 조회
- `PUT /api/change/<change_id>/departments` : 변경사항 부서 배정(전체 교체)

### 증빙자료(Registry)
- `GET /api/evidence?criterion=&cycle=` : 증빙자료 목록
- `POST /api/evidence` : 증빙자료 등록
- `PUT /api/evidence/<ev_id>` : 증빙자료 수정
- `DELETE /api/evidence/<ev_id>` : 증빙자료 삭제
- `GET /api/evidence/summary` : 준거별 요약

### AI (RAG)
- `POST /api/ai/ask`
  - `query`: 질문
  - `criterion`: (선택) 특정 준거 기반 질의
  - `context_type`: `summary | evidence | strategy | guide | general`

### 지식그래프
- `GET /api/graph/data` : vis.js 호환 그래프 데이터(노드/엣지)

---

## 5) 레포지토리 구조

```text
.
├── app.py                      # Flask 서버 + API/페이지 라우팅 + DB 초기화(추가 테이블)
├── ai_service.py               # LM Studio(OpenAI 호환) 연동 + 컨텍스트 구성(RAG)
├── accreditation_review.db     # SQLite DB (분석/검토 데이터)
├── import_to_sqlite.py         # JSONL 산출물 -> SQLite 임포트 + 인덱스/뷰 생성
├── verify_db.py                # DB 임포트/뷰 정상 동작 간단 검증 스크립트
├── templates/                  # HTML 템플릿
│   ├── dashboard.html
│   ├── review.html
│   ├── fullview.html
│   ├── evidence.html
│   └── graph.html
├── static/
│   └── css/
│       ├── style.css           # 공통 테마/컴포넌트 스타일
│       ├── review.css
│       ├── fullview.css
│       ├── evidence.css
│       └── graph.css
├── outputs-20260427T015448Z-3-001/   # (데이터 산출물) 임포트 원본
├── scripts-20260427T015447Z-3-001/   # (데이터 생성/가공) 스크립트 번들
├── PROJECT_HANDOVER.md         # 프로젝트 인수인계/주의사항/구조 설명(중요)
└── .gitignore
```

---

## 6) 데이터(DB) 관련

### DB 파일
- `accreditation_review.db`

### 추가로 자동 생성되는 테이블(app.py)
`app.py`의 `init_extra_tables()`에서 다음 테이블을 생성/시딩합니다.
- `review_log` : 상태 변경/메모 이력
- `departments` : 부서 마스터(기본 부서 seed 포함)
- `change_department` : 변경사항-부서 N:M 연결
- `evidence_registry` : 증빙자료 등록부

---

## 7) 데이터 임포트 (JSONL → SQLite)

레포 내 `outputs-20260427T015448Z-3-001/outputs` 산출물을 기준으로 DB를 재생성/임포트하려면:

```bash
python import_to_sqlite.py
```

임포트 후 간단 검증:

```bash
python verify_db.py
```

---

## 8) 참고 문서

- `PROJECT_HANDOVER.md` : 기능/구조/주의사항이 가장 상세하게 정리되어 있습니다.
