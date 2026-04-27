# 대학기관평가인증 4주기 준비 시스템 — Handover & 프로젝트 가이드

이 문서는 3주기 및 4주기 편람 비교 데이터를 바탕으로 구축된 **평가인증 관리 및 AI 어시스턴트 대시보드**의 구조와 핵심 구현 사항을 정리한 인수인계/가이드라인입니다. 새로운 세션에서 작업을 재개할 때 이 문서를 우선적으로 참고하세요.

---

## 1. 프로젝트 개요 및 기술 스택
- **목적:** 대학기관평가인증 4주기 편람 변경사항을 효과적으로 분석하고, 각 현업 부서의 증빙자료 준비 및 실무 대응을 관리하기 위함. 더불어 구축된 지식그래프를 바탕으로 RAG(검색 증강 생성) 기반 AI 어시스턴트를 제공.
- **실행 환경:** Python 3.x, Flask (⚠️ **Streamlit이 아닙니다.**)
- **DB:** SQLite (`accreditation_review.db`)
- **Frontend:** HTML5, Vanilla JavaScript, CSS3 (모던 다크 모드, Glassmorphism UI 적용), `vis.js` (그래프 시각화)
- **AI 연동:** `openai` 파이썬 패키지를 이용한 **로컬 LM Studio API**(`http://localhost:1234/v1`) 연결. (추후 클라우드 LLM 확장 가능)

---

## 2. 주요 기능 및 라우트 구조

| 기능 명칭 | URL 라우트 | 템플릿 파일 | 설명 |
| :--- | :--- | :--- | :--- |
| **현황 대시보드** | `/` | `dashboard.html` | 전체 진행률, 요약 통계 제공 |
| **전체 비교 뷰** | `/fullview` | `fullview.html` | 밀도 높은 테이블 구조로 3/4주기 항목을 전체 스캔하고 즉각 확정/반려 처리 |
| **상세 검토 뷰** | `/review` | `review.html` | 단일 준거에 대한 상세 변경사항 모달 제공 및 **담당 부서 복수 매칭** 기능 |
| **증빙 제출 관리** | `/submissions` | `submissions.html` | 부서 담당자 증빙 업로드, 파일 버전 이력, 관리자 보완요청/승인 |
| **증빙자료 관리** | `/evidence` | `evidence.html` | 3주기 자료 목록화 및 4주기 재활용 여부 CRUD 처리 (준거별 그룹핑) |
| **지식그래프 & AI** | `/graph` | `graph.html` | `vis.js`를 이용한 편람 간 연관성 시각화 및 AI(RAG) 기반 실무 가이드/요약 채팅 |

---

## 3. 핵심 DB 추가 스키마 (최근 작업분)
기존 코덱스가 생성한 `change_atom`, `department_action`, `graph_nodes`, `graph_edges` 외에 다음 테이블이 동적으로 자동 초기화(`init_extra_tables()`) 됩니다.

1. **`departments`**: 기준이 되는 대학 행정부서 마스터 테이블 (기획처, 교무처 등 16개 사전 셋업).
2. **`change_department`**: 준거별 변경사항(`change_id`)과 부서(`dept_id`)를 이어주는 다대다(N:M) 연결 테이블.
3. **`evidence_registry`**: 과거 증빙자료 관리 (자료 제목, 위치, 관리번호, 재활용 여부, 매칭된 준거 등).
4. **`users`**: 내부 MVP용 로그인 계정. 역할은 `admin`, `department`만 사용.
5. **`evidence_submission`**: `evidence_checklist` 항목별 제출 상태. 상태는 `not_submitted`, `submitted`, `revision_requested`, `approved`.
6. **`evidence_file`**: 제출 파일 버전 이력. `version_no`, 업로더 사용자 ID, 업로더 이메일 스냅샷, 서버 업로드시간, SHA-256 해시를 저장.
7. **`evidence_submission_log`**: 업로드 및 관리자 상태 변경 감사 로그.

### 개발용 계정
- 관리자: `admin@local.accreditation` / `admin1234`
- 부서 담당자 예시: `acad@local.accreditation` / `dept1234`
- 부서 계정은 부서 코드 기준으로 자동 시딩됩니다. 운영 전 비밀번호 변경 또는 SSO 전환이 필요합니다.

---

## 4. ⚠️ 중요: 반드시 지켜야 할 규칙 (DOs and DON'Ts)

### 🔴 절대 하지 말아야 할 것 (DON'Ts)
1. **`streamlit run app.py` 실행 금지:** 
   - 이 프로젝트는 Flask 애플리케이션입니다. 터미널에서 반드시 `python app.py`로 실행해야 합니다. Streamlit 명령어로 실행하면 포트가 충돌하거나 서버가 행(hang) 상태에 빠집니다.
2. **지식그래프 DB 컬럼명 혼동 주의:**
   - 엣지를 쿼리할 때 `graph_edges` 테이블에는 `source_id`가 아닌 `source_node_id`, `target_node_id`, `edge_type` 컬럼을 사용해야 합니다. (이 부분에서 과거 500 에러 발생 이력 있음)
3. **대규모 그래프 렌더링 물리(Physics) 켜기 금지:**
   - 편람 노드가 1,500개를 넘어갑니다. `vis.js` 옵션에서 `improvedLayout: false`를 유지하고 Physics 설정을 지나치게 무겁게 주면 브라우저 캔버스가 무한 확장(Height 18,000px 이상)되며 크래시납니다.

### 🟢 반드시 지켜야 할 사항 (DOs)
1. **UI 스타일 일관성:**
   - 버튼이나 배경색 등 UI 요소를 추가할 때는 반드시 `style.css` 상단에 정의된 CSS 변수(예: `var(--accent-indigo)`, `var(--bg-glass)`)를 사용해 다크 테마와 Glassmorphism 룩앤필을 유지하세요.
2. **RAG 파이프라인 (AI 컨텍스트):**
   - AI 답변의 정확도를 위해 `ai_service.py` 내의 `build_context_for_criterion` 함수가 존재합니다. 새로운 편람 분석 항목이 추가된다면 반드시 이 함수에도 쿼리를 추가하여 LLM이 참고할 수 있도록 컨텍스트를 확장해야 합니다.
3. **로컬 AI 서버 설정:**
   - 현재 LLM은 환경변수 설정이 없으면 `http://localhost:1234/v1`을 향하게 되어 있습니다. 다른 기기에서 테스트할 때 LM Studio의 "Local Server" 기능이 이 포트로 켜져 있는지 항상 먼저 확인하세요.

---

*문서 생성일: 2026-04-27*
