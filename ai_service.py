import sqlite3
import os
import json
from openai import OpenAI

# LM Studio 또는 OpenAI 호환 API 설정
AI_BASE_URL = os.getenv("AI_BASE_URL", "http://localhost:1234/v1")
AI_API_KEY = os.getenv("AI_API_KEY", "lm-studio")
AI_MODEL = os.getenv("AI_MODEL", "gemma-2-9b-it") # LM Studio는 일반적으로 첫번째 로드된 모델을 사용함

try:
    client = OpenAI(base_url=AI_BASE_URL, api_key=AI_API_KEY)
except Exception as e:
    print(f"⚠️ OpenAI Client 초기화 실패: {e}")
    client = None


def _format_ai_error(error: Exception) -> dict:
    message = str(error)

    if "No models loaded" in message:
        return {
            "error": "AI 모델이 아직 로드되지 않았습니다. LM Studio 개발자 페이지에서 모델을 먼저 로드하거나 `lms load`로 모델을 실행하세요.",
            "status_code": 503,
        }

    if "Connection refused" in message or "Failed to establish a new connection" in message:
        return {
            "error": "AI 서버에 연결할 수 없습니다. LM Studio가 실행 중인지 확인하세요.",
            "status_code": 503,
        }

    return {
        "error": f"AI 응답 오류: {message}",
        "status_code": 500,
    }


def build_dataset_catalog(conn):
    dataset_rows = conn.execute(
        """
        SELECT name, type
        FROM sqlite_master
        WHERE type IN ('table', 'view')
          AND name NOT LIKE 'sqlite_%'
        ORDER BY CASE type WHEN 'table' THEN 0 ELSE 1 END, name
        """
    ).fetchall()

    catalog_lines = []
    for row in dataset_rows:
        name = row[0]
        kind = row[1]
        catalog_lines.append(f"- {name} ({kind})")

    return "\n".join(catalog_lines)


def build_query_context(conn, query, criterion=None):
    query_text = (query or "").strip()
    lower_query = query_text.lower()

    if criterion:
        return build_context_for_criterion(conn, criterion)

    if any(term in query_text for term in ["데이터셋", "데이터 목록", "목록", "어떤 데이터", "무슨 데이터", "사용 가능한"]):
        catalog = build_dataset_catalog(conn)
        return "\n".join([
            "### 사용 가능한 데이터셋/뷰 ###",
            catalog,
            "",
            "이 데이터셋들을 근거로 질문에 답변하세요. 사용자에게 데이터셋을 다시 고르라고 묻지 마세요.",
        ])

    if any(term in query_text for term in ["신설", "새로", "신규", "추가", "새롭게"]):
        rows = conn.execute(
            """
            SELECT cycle4_criterion, cycle4_title, section_type, section_label,
                   change_type, similarity, source_text_3, source_text_4, review_reason
            FROM change_atom
                WHERE change_type LIKE '%신설%'
                    OR change_type LIKE '%new%'
            ORDER BY cycle4_criterion, section_type, similarity DESC
            LIMIT 40
            """
        ).fetchall()

        if rows:
            parts = ["### 4주기 신설 후보/신설 관련 항목 ###"]
            current_criterion = None
            for row in rows:
                row_criterion = row[0]
                if row_criterion != current_criterion:
                    current_criterion = row_criterion
                    parts.append(f"\n[준거 {row_criterion}] {row[1]}")
                similarity = row[5] if row[5] is not None else 0.0
                parts.append(
                    f"- {row[3]} / {row[2]} / {row[4]} / 유사도 {similarity:.3f}"
                )
                parts.append(f"  3주기: {row[6]}")
                parts.append(f"  4주기: {row[7]}")
                if row[8]:
                    parts.append(f"  사유: {row[8]}")
            return "\n".join(parts)

    overview_row = conn.execute(
        """
        SELECT
            COUNT(*) AS total_changes,
            SUM(CASE WHEN change_type LIKE '%신설%' OR change_type LIKE '%new%' THEN 1 ELSE 0 END) AS new_count,
            SUM(CASE WHEN change_type = '변경' THEN 1 ELSE 0 END) AS changed_count,
            SUM(CASE WHEN change_type LIKE '%삭제%' THEN 1 ELSE 0 END) AS deleted_count,
            COUNT(DISTINCT cycle4_criterion) AS total_criteria
        FROM change_atom
        """
    ).fetchone()

    top_new_rows = conn.execute(
        """
        SELECT cycle4_criterion, cycle4_title, COUNT(*) AS cnt
        FROM change_atom
        WHERE change_type LIKE '%신설%' OR change_type LIKE '%new%'
        GROUP BY cycle4_criterion, cycle4_title
        ORDER BY cnt DESC, cycle4_criterion
        LIMIT 12
        """
    ).fetchall()

    parts = [
        "### 편람 개요 컨텍스트 ###",
        f"총 변경사항: {overview_row[0]}건",
        f"신설 관련: {overview_row[1]}건",
        f"변경: {overview_row[2]}건",
        f"삭제 관련: {overview_row[3]}건",
        f"총 준거 수: {overview_row[4]}개",
    ]

    if top_new_rows:
        parts.append("")
        parts.append("### 신설 관련 상위 준거 ###")
        for row in top_new_rows:
            parts.append(f"- {row[0]} {row[1]} ({row[2]}건)")

    return "\n".join(parts)

def get_db_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def build_context_for_criterion(conn, criterion):
    """특정 준거에 대한 변경사항, 부서 조치, 증빙자료 컨텍스트 구성"""
    context_parts = []
    
    # 1. 변경사항 (change_atom)
    changes = conn.execute(
        "SELECT * FROM change_atom WHERE cycle4_criterion = ?", (criterion,)
    ).fetchall()
    
    if changes:
        context_parts.append(f"### [준거 {criterion}] 주요 변경사항 ###")
        for c in changes:
            context_parts.append(f"- 유형: {c['change_type']} | 섹션: {c['section_type']}")
            context_parts.append(f"  [3주기] {c['source_text_3']}")
            context_parts.append(f"  [4주기] {c['source_text_4']}")
            context_parts.append("")
            
    # 2. 관련 부서 조치 (department_action)
    actions = conn.execute(
        "SELECT * FROM department_action WHERE cycle4_criterion = ?", (criterion,)
    ).fetchall()
    
    if actions:
        context_parts.append(f"### [준거 {criterion}] 부서 조치사항 ###")
        for a in actions:
            context_parts.append(f"- 주관부서: {a['primary_department']} | 위험도: {a['risk_level']}")
            context_parts.append(f"  내용: {a['preparation_task']}")
            context_parts.append("")
            
    # 3. 기존 증빙자료 (evidence_registry)
    evidences = conn.execute(
        "SELECT * FROM evidence_registry WHERE criterion = ?", (criterion,)
    ).fetchall()
    
    if evidences:
        context_parts.append(f"### [준거 {criterion}] 기 등록된 증빙자료 ###")
        for e in evidences:
            reuse = "재활용 가능" if e['is_reusable'] else "갱신 필요"
            context_parts.append(f"- [{e['cycle']}주기] {e['doc_title']} ({reuse})")
            
    return "\n".join(context_parts)

def ask_ai(db_path, query, criterion=None, context_type="general"):
    """
    AI에게 질문하기
    context_type: 
      - summary (변경사항 요약)
      - evidence (증빙자료 추천)
      - strategy (대비 전략)
      - guide (부서 업무 가이드)
      - general (일반 질의 / 편람 해석)
    """
    if not client:
        return {"error": "AI 클라이언트가 연결되지 않았습니다. LM Studio가 실행 중인지 확인하세요."}
        
    conn = get_db_connection(db_path)
    context_text = build_query_context(conn, query, criterion)
    dataset_catalog = build_dataset_catalog(conn)
        
    conn.close()
    
    # 시스템 프롬프트 구성
    system_prompt = (
        "당신은 대학기관평가인증 4주기 준비를 돕는 AI 어시스턴트입니다.\n"
        "아래에 제공된 데이터셋과 문맥만 근거로 사용자(기획처 및 행정부서 실무자)의 질문에 전문적이고 명확하게 답변하세요.\n"
        "사용자에게 데이터셋 선택을 다시 묻지 마세요. 필요한 경우 현재 제공된 데이터셋 목록을 참고해 직접 답변하세요.\n"
        "데이터에 없는 내용은 추측하지 말고 모른다고 답변하세요.\n"
        "신설 여부가 후보 상태라면 '신설후보'라고 명시하고, 확정된 사실과 구분하세요."
    )
    system_prompt += f"\n\n[사용 가능한 데이터셋]\n{dataset_catalog}"
    
    if context_text:
        context_label = f"준거 {criterion}" if criterion else "질의 기반 문맥"
        system_prompt += f"\n\n[참고 데이터 - {context_label}]\n{context_text}"
        
    # 사용자 프롬프트 템플릿 적용
    if context_type == "summary":
        prompt = f"{criterion} 준거의 3주기 대비 4주기 주요 변경점을 3~5가지 불릿 포인트로 핵심만 요약해줘."
    elif context_type == "evidence":
        prompt = f"{criterion} 준거를 충족하기 위해 4주기에 새로 준비해야 하거나 보완해야 할 증빙자료 목록을 추천해줘."
    elif context_type == "strategy":
        prompt = f"{criterion} 준거에서 과거 3주기 지적사항을 고려할 때 4주기에 가장 주의해야 할 취약점과 대비 전략은 뭐야?"
    elif context_type == "guide":
        prompt = f"{criterion} 준거와 관련된 각 부서(교무처, 학생처 등)가 구체적으로 어떤 업무를 준비해야 하는지 가이드라인을 작성해줘."
    else:
        prompt = query

    try:
        response = client.chat.completions.create(
            model=AI_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=1000
        )
        return {"answer": response.choices[0].message.content, "context_used": bool(context_text)}
    except Exception as e:
        return _format_ai_error(e)
