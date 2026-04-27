"""
코덱스 작업산출물 → SQLite DB 임포트 스크립트
==============================================
JSONL 파일을 SQLite DB로 변환합니다.
- 모든 canonical_datasets + dashboard_mvp 테이블 임포트
- 적절한 컬럼 타입 추론 (TEXT / INTEGER / REAL / BOOLEAN)
- 인덱스 생성 (검토 워크플로우에 필요한 필드)
- 유용한 뷰(VIEW) 생성
"""

import json
import os
import sqlite3
import sys
from pathlib import Path
from datetime import datetime

# Windows cp949 인코딩 문제 방지
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

# ============================================================
# 설정
# ============================================================

SCRIPT_DIR = Path(__file__).parent
OUTPUTS_DIR = SCRIPT_DIR / "outputs-20260427T015448Z-3-001" / "outputs"
CANONICAL_DIR = OUTPUTS_DIR / "canonical_datasets"
DASHBOARD_DIR = OUTPUTS_DIR / "dashboard_mvp"
DB_PATH = SCRIPT_DIR / "accreditation_review.db"

# 숫자로 변환해야 하는 필드 (REAL)
REAL_FIELDS = {
    "similarity", "title_similarity", "score",
    "difflib_similarity", "ngram_jaccard", "token_overlap",
    "top_candidate_score",
}

# 정수로 변환해야 하는 필드 (INTEGER)
INTEGER_FIELDS = {
    "input_index", "rank", "priority", "item_no", "subitem_no",
    "occurrence_count", "global_candidate_count",
    "candidate_count", "confirmed_count", "needs_review_count",
    "high_risk_count", "medium_risk_count", "total_changes",
    "official_confirmation_needed_count", "action_count",
    "cycle",
}

# 불리언 필드 → INTEGER 0/1
BOOLEAN_FIELDS = {
    "manual_review_required", "official_confirmation_needed",
    "benchmark_required", "notice_required",
    "evidence_impact", "metric_impact",
    "criterion_mapping_match", "field_match", "section_match",
}

# 각 테이블의 기본키
PRIMARY_KEYS = {
    "canonical_source": "source_id",
    "candidate_metadata": "candidate_id",
    "canonical_mapping": "mapping_id",
    "change_atom": "change_id",
    "department_action": "action_id",
    "global_match_candidate": "match_id",
    "graph_edges": "edge_id",
    "graph_nodes": "node_id",
    "rag_chunks": "chunk_id",
    "review_queue": "review_id",
    "criterion_change_summary": None,  # cycle4_criterion을 PK로
    "department_action_summary": None,
    "evidence_checklist": "checklist_id",
    "high_risk_items": "action_id",
    "manual_review_queue": "review_id",
}

# ============================================================
# 유틸리티
# ============================================================

def convert_value(key: str, value):
    """필드 이름에 따라 적절한 Python 타입으로 변환"""
    if value is None or value == "":
        return None

    if key in REAL_FIELDS:
        try:
            return float(value)
        except (ValueError, TypeError):
            return None

    if key in INTEGER_FIELDS:
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    if key in BOOLEAN_FIELDS:
        if isinstance(value, bool):
            return 1 if value else 0
        s = str(value).lower().strip()
        if s in ("true", "1", "yes"):
            return 1
        elif s in ("false", "0", "no", ""):
            return 0
        return None

    # dict/list → JSON 문자열
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)

    return str(value)


def sqlite_type(key: str) -> str:
    """필드 이름 → SQLite 타입 문자열"""
    if key in REAL_FIELDS:
        return "REAL"
    if key in INTEGER_FIELDS:
        return "INTEGER"
    if key in BOOLEAN_FIELDS:
        return "INTEGER"  # 0/1
    return "TEXT"


def read_jsonl(filepath: Path) -> list[dict]:
    """JSONL 파일을 읽어 dict 리스트로 반환"""
    rows = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
                rows.append(obj)
            except json.JSONDecodeError as e:
                print(f"  ⚠ JSON 파싱 오류 (줄 {line_no}): {e}")
    return rows


def discover_columns(rows: list[dict]) -> list[str]:
    """모든 행에서 등장하는 컬럼을 순서 유지하며 수집"""
    seen = set()
    columns = []
    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                columns.append(key)
    return columns


# ============================================================
# 테이블 생성 및 데이터 삽입
# ============================================================

def import_table(conn: sqlite3.Connection, table_name: str, filepath: Path):
    """하나의 JSONL 파일을 테이블로 임포트"""
    print(f"\n{'='*60}")
    print(f"📥 테이블: {table_name}")
    print(f"   파일: {filepath.name}")

    rows = read_jsonl(filepath)
    if not rows:
        print("   ⚠ 데이터 없음, 건너뜀")
        return 0

    columns = discover_columns(rows)
    pk = PRIMARY_KEYS.get(table_name)

    # CREATE TABLE
    col_defs = []
    for col in columns:
        col_type = sqlite_type(col)
        if col == pk:
            col_defs.append(f'    "{col}" {col_type} PRIMARY KEY')
        else:
            col_defs.append(f'    "{col}" {col_type}')

    create_sql = f'CREATE TABLE IF NOT EXISTS "{table_name}" (\n'
    create_sql += ",\n".join(col_defs)
    create_sql += "\n);"

    conn.execute(f'DROP TABLE IF EXISTS "{table_name}"')
    conn.execute(create_sql)

    # INSERT
    placeholders = ", ".join(["?"] * len(columns))
    col_names = ", ".join([f'"{c}"' for c in columns])
    insert_sql = f'INSERT INTO "{table_name}" ({col_names}) VALUES ({placeholders})'

    converted_rows = []
    for row in rows:
        values = []
        for col in columns:
            raw = row.get(col)
            values.append(convert_value(col, raw))
        converted_rows.append(tuple(values))

    conn.executemany(insert_sql, converted_rows)
    conn.commit()

    print(f"   ✅ {len(converted_rows)}행 삽입 완료")
    print(f"   📋 컬럼 수: {len(columns)}")
    return len(converted_rows)


# ============================================================
# 인덱스 생성
# ============================================================

def create_indexes(conn: sqlite3.Connection):
    """검토 워크플로우에 필요한 인덱스 생성"""
    print(f"\n{'='*60}")
    print("🔍 인덱스 생성 중...")

    indexes = [
        # canonical_source
        ("idx_source_cycle", "canonical_source", "cycle"),
        ("idx_source_criterion", "canonical_source", "criterion"),
        ("idx_source_section_type", "canonical_source", "section_type"),
        ("idx_source_verification", "canonical_source", "verification_status"),

        # change_atom
        ("idx_change_c4_criterion", "change_atom", "cycle4_criterion"),
        ("idx_change_type", "change_atom", "change_type"),
        ("idx_change_verification", "change_atom", "verification_status"),
        ("idx_change_review_status", "change_atom", "human_review_status"),
        ("idx_change_section", "change_atom", "section_type"),
        ("idx_change_source3", "change_atom", "source_id_3"),
        ("idx_change_source4", "change_atom", "source_id_4"),

        # department_action
        ("idx_action_criterion", "department_action", "cycle4_criterion"),
        ("idx_action_risk", "department_action", "risk_level"),
        ("idx_action_change_id", "department_action", "change_id"),
        ("idx_action_dept", "department_action", "primary_department"),
        ("idx_action_verification", "department_action", "verification_status"),

        # review_queue
        ("idx_review_priority", "review_queue", "priority"),
        ("idx_review_risk", "review_queue", "risk_level"),
        ("idx_review_status", "review_queue", "human_review_status"),
        ("idx_review_c4_criterion", "review_queue", "cycle4_criterion"),
        ("idx_review_change_id", "review_queue", "change_id"),

        # canonical_mapping
        ("idx_mapping_c4", "canonical_mapping", "cycle4_criterion"),
        ("idx_mapping_c3", "canonical_mapping", "cycle3_criterion"),
        ("idx_mapping_verification", "canonical_mapping", "verification_status"),

        # global_match_candidate
        ("idx_gmatch_change_id", "global_match_candidate", "change_id"),
        ("idx_gmatch_rank", "global_match_candidate", "rank"),

        # graph
        ("idx_gedge_source", "graph_edges", "source_node_id"),
        ("idx_gedge_target", "graph_edges", "target_node_id"),
        ("idx_gnode_type", "graph_nodes", "node_type"),

        # dashboard_mvp
        ("idx_ccs_criterion", "criterion_change_summary", "cycle4_criterion"),
        ("idx_das_dept", "department_action_summary", "primary_department"),
        ("idx_ec_criterion", "evidence_checklist", "cycle4_criterion"),
        ("idx_hri_criterion", "high_risk_items", "cycle4_criterion"),
        ("idx_hri_risk", "high_risk_items", "risk_level"),
        ("idx_mrq_criterion", "manual_review_queue", "cycle4_criterion"),
        ("idx_mrq_priority", "manual_review_queue", "priority"),
    ]

    created = 0
    for idx_name, table, column in indexes:
        try:
            conn.execute(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON "{table}" ("{column}")')
            created += 1
        except sqlite3.OperationalError as e:
            print(f"   ⚠ {idx_name}: {e}")

    conn.commit()
    print(f"   ✅ {created}개 인덱스 생성 완료")


# ============================================================
# 뷰(VIEW) 생성
# ============================================================

def create_views(conn: sqlite3.Connection):
    """검토 워크플로우에 유용한 뷰 생성"""
    print(f"\n{'='*60}")
    print("📊 뷰(VIEW) 생성 중...")

    views = {
        # 1. 준거별 검토 진행률
        "v_criterion_review_progress": """
            SELECT
                ca.cycle4_criterion,
                ca.cycle4_title,
                COUNT(*) AS total_changes,
                SUM(CASE WHEN ca.verification_status = 'confirmed' THEN 1 ELSE 0 END) AS confirmed,
                SUM(CASE WHEN ca.verification_status = 'needs_review' THEN 1 ELSE 0 END) AS needs_review,
                SUM(CASE WHEN ca.verification_status = 'candidate' THEN 1 ELSE 0 END) AS candidate,
                ROUND(100.0 * SUM(CASE WHEN ca.verification_status = 'confirmed' THEN 1 ELSE 0 END) / COUNT(*), 1) AS confirmed_pct,
                SUM(CASE WHEN ca.change_type = '유지' THEN 1 ELSE 0 END) AS cnt_maintained,
                SUM(CASE WHEN ca.change_type = '변경' THEN 1 ELSE 0 END) AS cnt_changed,
                SUM(CASE WHEN ca.change_type = '신설후보' THEN 1 ELSE 0 END) AS cnt_new,
                SUM(CASE WHEN ca.change_type IN ('삭제후보', '삭제/이동후보') THEN 1 ELSE 0 END) AS cnt_deleted,
                SUM(CASE WHEN ca.change_type = '이동후보' THEN 1 ELSE 0 END) AS cnt_moved
            FROM change_atom ca
            GROUP BY ca.cycle4_criterion, ca.cycle4_title
            ORDER BY ca.cycle4_criterion
        """,

        # 2. 변경사항 + 원문 비교 뷰 (핵심 검토 화면용)
        "v_change_detail": """
            SELECT
                ca.change_id,
                ca.change_type,
                ca.cycle4_criterion,
                ca.cycle4_title,
                ca.cycle3_criterion,
                ca.cycle3_title,
                ca.section_type,
                ca.section_label,
                ca.similarity,
                ca.source_text_3,
                ca.source_text_4,
                ca.source_id_3,
                ca.source_id_4,
                ca.verification_status,
                ca.human_review_status,
                ca.official_confirmation_needed,
                ca.global_match_status,
                ca.global_candidate_count,
                ca.review_reason,
                ca.manual_review_required,
                ca.change_categories
            FROM change_atom ca
            ORDER BY ca.cycle4_criterion, ca.section_type, ca.change_id
        """,

        # 3. 부서별 업무량 요약
        "v_department_workload": """
            SELECT
                da.primary_department,
                COUNT(*) AS total_actions,
                SUM(CASE WHEN da.risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk,
                SUM(CASE WHEN da.risk_level = 'medium' THEN 1 ELSE 0 END) AS medium_risk,
                SUM(CASE WHEN da.official_confirmation_needed = 1 THEN 1 ELSE 0 END) AS needs_confirmation,
                GROUP_CONCAT(DISTINCT da.cycle4_criterion) AS related_criteria
            FROM department_action da
            WHERE da.primary_department IS NOT NULL AND da.primary_department != ''
            GROUP BY da.primary_department
            ORDER BY total_actions DESC
        """,

        # 4. 고위험 검토 대기열 (검토 우선순위용)
        "v_high_priority_review": """
            SELECT
                rq.review_id,
                rq.priority,
                rq.risk_level,
                rq.cycle4_criterion,
                rq.cycle4_title,
                rq.change_type,
                rq.section_type,
                rq.review_reason,
                rq.human_review_status,
                rq.global_match_status,
                rq.top_candidate_score,
                rq.recommended_next_step,
                ca.source_text_3,
                ca.source_text_4,
                ca.similarity
            FROM review_queue rq
            LEFT JOIN change_atom ca ON rq.change_id = ca.change_id
            WHERE rq.risk_level = 'high'
            ORDER BY rq.priority, rq.cycle4_criterion
        """,

        # 5. 3주기↔4주기 매핑 현황
        "v_mapping_overview": """
            SELECT
                cm.mapping_id,
                cm.cycle4_criterion,
                cm.cycle4_title,
                cm.cycle3_criterion,
                cm.cycle3_title,
                cm.raw_mapping_types,
                cm.title_similarity,
                cm.verification_status,
                cm.manual_review_required,
                cm.candidate_basis
            FROM canonical_mapping cm
            ORDER BY cm.cycle4_criterion, cm.cycle3_criterion
        """,

        # 6. 섹션 유형별 변경 통계
        "v_section_change_stats": """
            SELECT
                ca.section_type,
                COUNT(*) AS total,
                SUM(CASE WHEN ca.change_type = '유지' THEN 1 ELSE 0 END) AS maintained,
                SUM(CASE WHEN ca.change_type = '변경' THEN 1 ELSE 0 END) AS changed,
                SUM(CASE WHEN ca.change_type = '신설후보' THEN 1 ELSE 0 END) AS new_candidate,
                SUM(CASE WHEN ca.change_type IN ('삭제후보', '삭제/이동후보') THEN 1 ELSE 0 END) AS deleted,
                SUM(CASE WHEN ca.change_type = '이동후보' THEN 1 ELSE 0 END) AS moved
            FROM change_atom ca
            GROUP BY ca.section_type
            ORDER BY total DESC
        """,

        # 7. 글로벌 매칭 후보 상세 (change_id별 top-3)
        "v_top_match_candidates": """
            SELECT
                gmc.change_id,
                gmc.rank,
                gmc.score,
                gmc.candidate_source_id,
                gmc.candidate_text,
                gmc.query_source_id,
                gmc.query_text,
                gmc.match_reason,
                ca.change_type,
                ca.cycle4_criterion
            FROM global_match_candidate gmc
            LEFT JOIN change_atom ca ON gmc.change_id = ca.change_id
            WHERE gmc.rank <= 3
            ORDER BY gmc.change_id, gmc.rank
        """,
    }

    for view_name, view_sql in views.items():
        try:
            conn.execute(f'DROP VIEW IF EXISTS "{view_name}"')
            conn.execute(f'CREATE VIEW "{view_name}" AS {view_sql}')
            print(f"   ✅ {view_name}")
        except sqlite3.OperationalError as e:
            print(f"   ⚠ {view_name}: {e}")

    conn.commit()


# ============================================================
# 메타 테이블 (임포트 정보 기록)
# ============================================================

def create_meta_table(conn: sqlite3.Connection, stats: dict):
    """임포트 메타 정보를 기록하는 테이블"""
    conn.execute("DROP TABLE IF EXISTS _import_meta")
    conn.execute("""
        CREATE TABLE _import_meta (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)

    meta = {
        "import_timestamp": datetime.now().isoformat(),
        "source_directory": str(OUTPUTS_DIR),
        "db_path": str(DB_PATH),
        "total_tables": str(stats["total_tables"]),
        "total_rows": str(stats["total_rows"]),
        "codex_qa_report_date": "2026-04-27",
    }

    for k, v in meta.items():
        conn.execute("INSERT INTO _import_meta (key, value) VALUES (?, ?)", (k, v))

    # 테이블별 행 수도 기록
    for table_name, count in stats["table_counts"].items():
        conn.execute(
            "INSERT INTO _import_meta (key, value) VALUES (?, ?)",
            (f"table_rows:{table_name}", str(count)),
        )

    conn.commit()
    print(f"\n   ✅ 메타 정보 기록 완료")


# ============================================================
# 메인
# ============================================================

def main():
    print("=" * 60)
    print("🚀 코덱스 작업산출물 → SQLite DB 임포트")
    print(f"   DB 경로: {DB_PATH}")
    print(f"   데이터 경로: {OUTPUTS_DIR}")
    print("=" * 60)

    # 경로 확인
    if not CANONICAL_DIR.exists():
        print(f"❌ canonical_datasets 디렉토리가 없습니다: {CANONICAL_DIR}")
        sys.exit(1)
    if not DASHBOARD_DIR.exists():
        print(f"❌ dashboard_mvp 디렉토리가 없습니다: {DASHBOARD_DIR}")
        sys.exit(1)

    # DB 연결
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    stats = {"total_tables": 0, "total_rows": 0, "table_counts": {}}

    # ── canonical_datasets 임포트 ──
    canonical_files = [
        "canonical_source",
        "candidate_metadata",
        "canonical_mapping",
        "change_atom",
        "department_action",
        "global_match_candidate",
        "graph_edges",
        "graph_nodes",
        "rag_chunks",
        "review_queue",
    ]

    for table_name in canonical_files:
        filepath = CANONICAL_DIR / f"{table_name}.jsonl"
        if filepath.exists():
            count = import_table(conn, table_name, filepath)
            stats["total_tables"] += 1
            stats["total_rows"] += count
            stats["table_counts"][table_name] = count
        else:
            print(f"\n⚠ 파일 없음: {filepath.name}")

    # ── dashboard_mvp 임포트 ──
    dashboard_files = [
        "criterion_change_summary",
        "department_action_summary",
        "evidence_checklist",
        "high_risk_items",
        "manual_review_queue",
    ]

    for table_name in dashboard_files:
        filepath = DASHBOARD_DIR / f"{table_name}.jsonl"
        if filepath.exists():
            count = import_table(conn, table_name, filepath)
            stats["total_tables"] += 1
            stats["total_rows"] += count
            stats["table_counts"][table_name] = count
        else:
            print(f"\n⚠ 파일 없음: {filepath.name}")

    # ── 인덱스 생성 ──
    create_indexes(conn)

    # ── 뷰 생성 ──
    create_views(conn)

    # ── 메타 테이블 ──
    create_meta_table(conn, stats)

    # ── 최종 요약 ──
    print(f"\n{'='*60}")
    print("🎉 임포트 완료!")
    print(f"   📁 DB 파일: {DB_PATH}")
    print(f"   📊 테이블: {stats['total_tables']}개")
    print(f"   📝 총 행 수: {stats['total_rows']:,}개")
    print(f"\n   테이블별 행 수:")
    for table_name, count in stats["table_counts"].items():
        print(f"     - {table_name}: {count:,}행")

    # DB 파일 크기
    db_size = DB_PATH.stat().st_size
    if db_size > 1024 * 1024:
        print(f"\n   💾 DB 크기: {db_size / (1024*1024):.1f} MB")
    else:
        print(f"\n   💾 DB 크기: {db_size / 1024:.1f} KB")

    conn.close()
    print(f"\n{'='*60}")


if __name__ == "__main__":
    main()
