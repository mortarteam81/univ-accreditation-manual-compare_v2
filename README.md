# 대학기관평가인증 편람 비교·검토 대시보드 (3주기 ↔ 4주기)

3주기 대학기관평가인증 편람과 4주기 대학기관평가인증 편람을 **준거(criterion) 단위로 비교/분석**하고, 변경사항 검토(확정/보류/반려), 부서 배정, 증빙자료 관리, 그리고 **로컬 LLM(LM Studio) 기반 AI 질의(RAG)** 를 제공하는 Flask 대시보드입니다.

- Backend: **Python / Flask**
- DB: **SQLite** (`accreditation_review.db`)
- Frontend: **HTML + Vanilla JS + CSS**
- Graph: **vis.js** 기반 지식그래프 시각화
- AI: `openai` SDK를 사용해 **LM Studio(OpenAI-compatible) 로컬 API** 연동
- 제출 포털: 부서별 증빙 업로드, 파일 버전 이력, 관리자 보완요청/승인

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

### 3. 인증 환경변수

기본 인증은 Google OIDC입니다. 운영/공유 환경에서는 아래 값을 설정하세요.

```bash
export FLASK_SECRET_KEY="change-to-a-long-random-secret"
export OIDC_CLIENT_ID="google-oauth-client-id"
export OIDC_CLIENT_SECRET="google-oauth-client-secret"
export OIDC_SERVER_METADATA_URL="https://accounts.google.com/.well-known/openid-configuration"
export OIDC_REDIRECT_URI="http://localhost:5001/auth/oidc/callback"
export INITIAL_ADMIN_EMAILS="admin@example.com"
```

선택적으로 `AUTH_USER_SEED_PATH`에 CSV 경로를 지정하면 사용자 allowlist를 시딩할 수 있습니다.
CSV 컬럼은 `email,display_name,role,department,is_active`를 사용합니다.

로컬 개발에서만 기존 비밀번호 로그인을 쓰려면 명시적으로 켭니다.

```bash
export DEV_AUTH_ENABLED=1
```

### 4. 실행

> ⚠️ 이 프로젝트는 Streamlit이 아니라 **Flask** 입니다.

```bash
python app.py
```

실행 후:
- http://localhost:5000 접속

### 5. 개발용 로그인 계정

`DEV_AUTH_ENABLED=1`일 때만 내부 MVP용 계정으로 로그인할 수 있습니다. 운영에서는 Google OIDC와 `users` allowlist를 사용하세요.

| 역할 | 이메일 | 기본 비밀번호 |
|---|---|---|
| 관리자 | `admin@local.accreditation` | `admin1234` |
| 부서 담당자 예시 | `acad@local.accreditation` | `dept1234` |

부서 계정은 부서 마스터 코드 기준으로 생성됩니다. 예: `plan@local.accreditation`, `stud@local.accreditation`, `libr@local.accreditation`.

모든 페이지와 API는 로그인 후 접근합니다. 관리자는 전체 데이터를 조회/변경할 수 있고, 부서 담당자는 자기 부서와 관련된 편람 비교 항목 및 제출 항목만 조회합니다. 편람 비교의 확정/반려/보류는 관리자만 가능하며, 부서 담당자는 관련 항목에 부서 의견 메모를 남길 수 있습니다.

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
| 증빙 제출 관리 | `/submissions` | `templates/submissions.html` |
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
  - 응답에는 Phase 1.5 복합 매칭 후보(`composite_candidates`)도 포함됩니다.
  - 복합 후보는 기존 1:1 결과를 덮어쓰지 않고 `many_to_one`, `one_to_many`, `many_to_many` 가능성을 별도로 제시합니다.

### Phase 1.5 복합 매칭

단일 1:1 유사도만으로 설명하기 어려운 통합·분리·재구성 사례를 잡기 위해 `composite_matching.py`를 제공합니다.
기본 `change_atom` 생성 단계에서는 같은 raw group 안에서 4주기 항목 순서대로 3주기 항목을 소모하지 않고, 그룹 전체의 유사도 합이 최대가 되는 1:1 조합을 먼저 선택합니다. 이 보정은 `3주기 자체평가 실시 현황`처럼 뒤쪽 4주기 항목과 더 강하게 연결되는 후보가 앞쪽 항목에 먼저 배정되는 문제를 줄이기 위한 것입니다.

```bash
python composite_matching.py --rebuild --json-summary
```

이 명령은 `composite_match_candidate`와 `composite_match_link`를 재생성하며, 기존 `change_atom`, `global_match_candidate`, 검토 메모와 상태값은 변경하지 않습니다. 이미 저장된 복합 후보의 검토 상태, 결정 메모, 반영 이력은 같은 `composite_id` 기준으로 보존됩니다.
대표 사례는 `3주기 1.1 + 1.2 → 4주기 1.1`처럼 복수 원문이 하나의 4주기 원문을 설명하는 경우입니다.
이미 1:1로 직접 매핑된 항목과 삭제/이동 후보가 같은 4주기 원문으로 통합되는 경우도 `직접매핑+후보 통합 후보`로 함께 탐지합니다.
또한 `3주기 1.2 발전계획`처럼 한 원 준거가 두 개 이상의 4주기 준거에 나뉘어 연결될 수 있는 경우를 위해 제한적인 `개념 브릿지`를 적용합니다. 이 후보는 자동 확정하지 않고, 상세 화면의 `항목별 귀속 판단`에서 주 귀속·보조 연결·공통 근거·이동/분할 후보를 구분해 표시합니다.

### 검토 워크플로우
- `PATCH /api/change/<change_id>/status` : 검토 상태 업데이트
  - `status`: `confirmed | needs_review | rejected | deferred`
  - 관리자 전용, `X-CSRF-Token` 필요
- `PATCH /api/composite/<composite_id>/review` : 복합 매칭 후보 검토 상태 저장
  - `review_status`: `candidate | approved | rejected | needs_review`
  - 관리자 전용, `composite_match_log`에 승인/반려/재검토 이력을 저장
- `POST /api/composite/<composite_id>/apply` : 승인된 복합 후보를 관련 변경항목에 반영
  - `candidate` 또는 `deferred` 상태의 관련 항목은 `needs_review`로 이동
  - 이미 확정/반려/검토필요 상태인 항목은 상태를 덮어쓰지 않고 `composite_match` 메모만 남김
- `PATCH /api/match-candidate/<match_id>/review` : AI 1:1 후보 승인/반려/재검토 상태 저장
  - 관리자 전용, `match_candidate_log`에 후보 검토 이력을 저장
- `POST /api/match-candidate/<match_id>/apply` : 승인된 AI 후보를 실제 1:1 비교쌍에 반영
  - 대상 `change_atom`의 3주기/4주기 원문 링크와 유사도를 갱신하고, 같은 원문을 물고 있던 충돌 항목은 중복을 풀어 `needs_review`로 돌림
  - 기존 후보 등록 이력(`applied_at`)과 실제 매칭 적용 이력(`mapping_applied_at`)은 분리해 저장
- `POST /api/match-candidate/<match_id>/promote-composite` : AI 1:1 후보와 충돌 항목을 복합 후보로 승격
  - 한 원문이 복수 항목과 연결되는 경우 `composite_match_candidate`에 별도 후보로 등록
- `POST /api/change/<change_id>/note` : 검토 메모 추가
  - 관리자는 일반 메모(`note`), 부서 담당자는 부서 의견(`department_note`)으로 감사로그에 저장
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

### 증빙 제출 포털
- `GET /api/me` : 현재 로그인 사용자
- `GET /api/submissions?status=&criterion=&department=` : 제출 과제 목록
- `GET /api/submissions/<submission_id>/files` : 파일 버전 이력
- `POST /api/submissions/<submission_id>/upload` : 증빙 파일 업로드
- `GET /api/files/<file_id>/download` : 권한 확인 후 파일 다운로드
- `PATCH /api/submissions/<submission_id>/status` : 관리자 보완요청/승인

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
│   ├── login.html
│   ├── submissions.html
│   └── graph.html
├── static/
│   └── css/
│       ├── style.css           # 공통 테마/컴포넌트 스타일
│       ├── review.css
│       ├── fullview.css
│       ├── evidence.css
│       ├── submissions.css
│       └── graph.css
├── uploads/                    # 증빙 제출 파일 저장소(로컬 MVP)
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
- `users` : 내부 MVP용 사용자/역할/부서 계정
- `evidence_submission` : `evidence_checklist` 기반 제출 상태
- `evidence_file` : 파일 버전, 업로더 이메일 스냅샷, 서버 업로드시간, 해시
- `evidence_submission_log` : 업로드/상태 변경 이력

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
