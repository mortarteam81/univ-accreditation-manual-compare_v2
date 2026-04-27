"""
인증평가 편람 비교분석 대시보드 — Flask 서버
=============================================
SQLite DB에서 데이터를 읽어 JSON API로 제공합니다.
"""

import sqlite3
import json
import sys
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request

from ai_service import ask_ai

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

app = Flask(__name__)

DB_PATH = Path(__file__).parent / "accreditation_review.db"


# ─── DB 헬퍼 ───────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def query_all(sql, params=()):
    conn = get_db()
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def query_one(sql, params=()):
    conn = get_db()
    row = conn.execute(sql, params).fetchone()
    conn.close()
    return dict(row) if row else None


# ─── DB 초기화: 추가 테이블 ────────────────────────────

def init_extra_tables():
    conn = get_db()

    # 검토 로그
    conn.execute("""
        CREATE TABLE IF NOT EXISTS review_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            change_id TEXT NOT NULL,
            action TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT,
            note TEXT,
            reviewer TEXT DEFAULT 'user',
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_rlog_change ON review_log(change_id)")

    # 부서 마스터
    conn.execute("""
        CREATE TABLE IF NOT EXISTS departments (
            dept_id INTEGER PRIMARY KEY AUTOINCREMENT,
            dept_name TEXT NOT NULL UNIQUE,
            dept_code TEXT,
            category TEXT DEFAULT '행정',
            sort_order INTEGER DEFAULT 999,
            is_active INTEGER DEFAULT 1,
            created_at TEXT
        )
    """)

    # 변경사항-부서 다대다 연결
    conn.execute("""
        CREATE TABLE IF NOT EXISTS change_department (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            change_id TEXT NOT NULL,
            dept_id INTEGER NOT NULL,
            role TEXT DEFAULT '관련',
            assigned_by TEXT DEFAULT 'user',
            created_at TEXT,
            UNIQUE(change_id, dept_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cd_change ON change_department(change_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_cd_dept ON change_department(dept_id)")

    # 증빙자료 등록부
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_registry (
            ev_id INTEGER PRIMARY KEY AUTOINCREMENT,
            cycle TEXT NOT NULL DEFAULT '3',
            criterion TEXT NOT NULL,
            doc_title TEXT NOT NULL,
            doc_number TEXT,
            doc_location TEXT,
            notes TEXT,
            is_reusable INTEGER DEFAULT 1,
            created_by TEXT DEFAULT 'user',
            created_at TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ev_criterion ON evidence_registry(criterion)")

    # 기존 부서 시딩 (중복 무시)
    seed_depts = [
        ('기획처', 'PLAN', '행정', 1),
        ('교무처', 'ACAD', '행정', 2),
        ('학생처', 'STUD', '행정', 3),
        ('총무처', 'ADMN', '행정', 4),
        ('연구처', 'RSCH', '행정', 5),
        ('대외협력처', 'EXTR', '행정', 6),
        ('입학처', 'ADMS', '행정', 7),
        ('사회공헌 담당부서', 'SOCL', '행정', 8),
        ('교수학습지원센터', 'CTLT', '센터', 10),
        ('학생상담센터', 'CNSL', '센터', 11),
        ('진로·취창업지원센터', 'CARR', '센터', 12),
        ('도서관', 'LIBR', '기관', 13),
        ('시설관리팀', 'FCLT', '팀', 14),
        ('정보전산원', 'ITCR', '기관', 15),
        ('국제교류처', 'INTL', '행정', 16),
        ('대학원', 'GRAD', '기관', 17),
    ]
    now = datetime.now().isoformat()
    for name, code, cat, order in seed_depts:
        conn.execute("""
            INSERT OR IGNORE INTO departments (dept_name, dept_code, category, sort_order, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (name, code, cat, order, now))

    conn.commit()
    conn.close()

init_extra_tables()


# ─── 페이지 라우트 ──────────────────────────────────────

@app.route("/")
def dashboard():
    return render_template("dashboard.html")


@app.route("/review")
def review_page():
    return render_template("review.html")


@app.route("/fullview")
def fullview_page():
    return render_template("fullview.html")


@app.route("/api/fullview")
def api_fullview():
    """섹션 유형별 전체 변경사항 (준거별 그룹핑)"""
    section = request.args.get("section", "overview")

    rows = query_all("""
        SELECT
            ca.change_id, ca.change_type, ca.cycle4_criterion, ca.cycle4_title,
            ca.cycle3_criterion, ca.cycle3_title, ca.section_type, ca.section_label,
            ca.similarity, ca.source_text_3, ca.source_text_4,
            ca.source_id_3, ca.source_id_4, ca.verification_status,
            ca.human_review_status, ca.global_match_status, ca.global_candidate_count,
            ca.item_path_4, ca.field_name_4, ca.review_reason
        FROM change_atom ca
        WHERE ca.section_type = ?
        ORDER BY ca.cycle4_criterion, ca.change_id
    """, (section,))

    # Group by criterion
    grouped = {}
    for r in rows:
        key = r["cycle4_criterion"]
        if key not in grouped:
            grouped[key] = {"criterion": key, "title": r["cycle4_title"], "items": []}
        grouped[key]["items"].append(r)

    return jsonify(list(grouped.values()))


# ─── API 엔드포인트 ─────────────────────────────────────

@app.route("/api/overview")
def api_overview():
    """전체 현황 통계"""
    stats = {}

    # 총 변경사항 수
    r = query_one("SELECT COUNT(*) as cnt FROM change_atom")
    stats["total_changes"] = r["cnt"]

    # 검증 상태별
    rows = query_all("""
        SELECT verification_status, COUNT(*) as cnt
        FROM change_atom GROUP BY verification_status
    """)
    stats["verification_counts"] = {r["verification_status"]: r["cnt"] for r in rows}

    # 변경 유형별
    rows = query_all("""
        SELECT change_type, COUNT(*) as cnt
        FROM change_atom GROUP BY change_type ORDER BY cnt DESC
    """)
    stats["change_type_counts"] = {r["change_type"]: r["cnt"] for r in rows}

    # 위험도별 (department_action 기준)
    rows = query_all("""
        SELECT risk_level, COUNT(*) as cnt
        FROM department_action GROUP BY risk_level
    """)
    stats["risk_counts"] = {r["risk_level"]: r["cnt"] for r in rows}

    # 검토 상태별
    rows = query_all("""
        SELECT human_review_status, COUNT(*) as cnt
        FROM change_atom GROUP BY human_review_status
    """)
    stats["review_status_counts"] = {r["human_review_status"]: r["cnt"] for r in rows}

    # 총 준거 수
    r = query_one("SELECT COUNT(DISTINCT cycle4_criterion) as cnt FROM change_atom")
    stats["total_criteria"] = r["cnt"]

    # 원문 수
    r = query_one("SELECT COUNT(*) as cnt FROM canonical_source")
    stats["total_sources"] = r["cnt"]

    # 매핑 수
    r = query_one("SELECT COUNT(*) as cnt FROM canonical_mapping")
    stats["total_mappings"] = r["cnt"]

    return jsonify(stats)


@app.route("/api/criteria-progress")
def api_criteria_progress():
    """준거별 검토 진행률"""
    rows = query_all("SELECT * FROM v_criterion_review_progress")
    return jsonify(rows)


@app.route("/api/section-stats")
def api_section_stats():
    """섹션 유형별 변경 통계"""
    rows = query_all("SELECT * FROM v_section_change_stats")
    return jsonify(rows)


@app.route("/api/department-workload")
def api_department_workload():
    """부서별 업무량"""
    rows = query_all("SELECT * FROM v_department_workload")
    return jsonify(rows)


@app.route("/api/mapping-overview")
def api_mapping_overview():
    """3↔4주기 준거 매핑 현황"""
    rows = query_all("SELECT * FROM v_mapping_overview")
    return jsonify(rows)


@app.route("/api/criteria-list")
def api_criteria_list():
    """준거 목록 (필터용)"""
    rows = query_all("""
        SELECT DISTINCT cycle4_criterion, cycle4_title
        FROM change_atom
        ORDER BY cycle4_criterion
    """)
    return jsonify(rows)


@app.route("/api/changes")
def api_changes():
    """변경사항 목록 (필터 지원)"""
    criterion = request.args.get("criterion", "")
    section = request.args.get("section", "")
    change_type = request.args.get("change_type", "")
    status = request.args.get("status", "")

    sql = "SELECT * FROM v_change_detail WHERE 1=1"
    params = []

    if criterion:
        sql += " AND cycle4_criterion = ?"
        params.append(criterion)
    if section:
        sql += " AND section_type = ?"
        params.append(section)
    if change_type:
        sql += " AND change_type = ?"
        params.append(change_type)
    if status:
        sql += " AND verification_status = ?"
        params.append(status)

    rows = query_all(sql, params)
    return jsonify(rows)


@app.route("/api/change/<change_id>")
def api_change_detail(change_id):
    """변경사항 상세 + 매칭 후보"""
    change = query_one(
        "SELECT * FROM v_change_detail WHERE change_id = ?",
        (change_id,),
    )
    if not change:
        return jsonify({"error": "not found"}), 404

    # 관련 매칭 후보
    candidates = query_all(
        "SELECT * FROM v_top_match_candidates WHERE change_id = ?",
        (change_id,),
    )

    # 관련 부서 조치사항
    actions = query_all(
        "SELECT * FROM department_action WHERE change_id = ?",
        (change_id,),
    )

    return jsonify({
        "change": change,
        "match_candidates": candidates,
        "department_actions": actions,
    })


@app.route("/api/risk-heatmap")
def api_risk_heatmap():
    """준거×섹션 위험도 히트맵 데이터"""
    rows = query_all("""
        SELECT
            da.cycle4_criterion,
            da.section_type,
            COUNT(*) as total,
            SUM(CASE WHEN da.risk_level = 'high' THEN 1 ELSE 0 END) as high_cnt,
            SUM(CASE WHEN da.risk_level = 'medium' THEN 1 ELSE 0 END) as medium_cnt
        FROM department_action da
        GROUP BY da.cycle4_criterion, da.section_type
        ORDER BY da.cycle4_criterion, da.section_type
    """)
    return jsonify(rows)


# ─── 검토 워크플로우 API ─────────────────────────────────

@app.route("/api/change/<change_id>/status", methods=["PATCH"])
def api_update_status(change_id):
    """변경사항의 검토 상태를 업데이트"""
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")  # confirmed / needs_review / rejected
    note = data.get("note", "")
    reviewer = data.get("reviewer", "user")

    valid = {"confirmed", "needs_review", "rejected", "deferred"}
    if new_status not in valid:
        return jsonify({"error": f"Invalid status. Use: {valid}"}), 400

    conn = get_db()

    # 현재 상태 가져오기
    row = conn.execute(
        "SELECT verification_status, human_review_status FROM change_atom WHERE change_id = ?",
        (change_id,),
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "change not found"}), 404

    old_status = row["verification_status"]
    now = datetime.now().isoformat()

    # 상태 업데이트
    review_status_map = {
        "confirmed": "approved",
        "rejected": "rejected",
        "needs_review": "pending",
        "deferred": "deferred",
    }
    conn.execute("""
        UPDATE change_atom
        SET verification_status = ?,
            human_review_status = ?
        WHERE change_id = ?
    """, (new_status, review_status_map[new_status], change_id))

    # 로그 기록
    log_cursor = conn.execute("""
        INSERT INTO review_log (change_id, action, old_status, new_status, note, reviewer, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (change_id, "status_change", old_status, new_status, note, reviewer, now))

    conn.commit()

    saved = conn.execute("""
        SELECT change_id, verification_status, human_review_status
        FROM change_atom
        WHERE change_id = ?
    """, (change_id,)).fetchone()
    conn.close()

    return jsonify({
        "ok": True,
        "change_id": change_id,
        "old_status": old_status,
        "new_status": new_status,
        "review_log_id": log_cursor.lastrowid,
        "saved": dict(saved) if saved else None,
    })


@app.route("/api/change/<change_id>/note", methods=["POST"])
def api_add_note(change_id):
    """변경사항에 검토 메모를 추가"""
    data = request.get_json()
    note = data.get("note", "").strip()
    reviewer = data.get("reviewer", "user")

    if not note:
        return jsonify({"error": "note is empty"}), 400

    conn = get_db()
    now = datetime.now().isoformat()

    conn.execute("""
        INSERT INTO review_log (change_id, action, note, reviewer, created_at)
        VALUES (?, 'note', ?, ?, ?)
    """, (change_id, note, reviewer, now))

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "change_id": change_id})


@app.route("/api/change/<change_id>/history")
def api_change_history(change_id):
    """변경사항의 검토 이력"""
    rows = query_all(
        "SELECT * FROM review_log WHERE change_id = ? ORDER BY created_at DESC",
        (change_id,),
    )
    return jsonify(rows)


# ─── 부서 매칭 API ──────────────────────────────────────

@app.route("/api/departments")
def api_departments():
    """부서 마스터 목록"""
    rows = query_all("SELECT * FROM departments WHERE is_active=1 ORDER BY sort_order")
    return jsonify(rows)


@app.route("/api/departments", methods=["POST"])
def api_add_department():
    """부서 추가"""
    data = request.get_json()
    name = data.get("dept_name", "").strip()
    if not name:
        return jsonify({"error": "dept_name required"}), 400
    conn = get_db()
    now = datetime.now().isoformat()
    try:
        conn.execute(
            "INSERT INTO departments (dept_name, dept_code, category, created_at) VALUES (?,?,?,?)",
            (name, data.get("dept_code", ""), data.get("category", "행정"), now),
        )
        conn.commit()
    except Exception:
        conn.close()
        return jsonify({"error": "이미 존재하는 부서입니다"}), 409
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/change/<change_id>/departments")
def api_get_change_depts(change_id):
    """변경사항에 배정된 부서 목록"""
    rows = query_all("""
        SELECT cd.*, d.dept_name, d.dept_code, d.category
        FROM change_department cd
        JOIN departments d ON cd.dept_id = d.dept_id
        WHERE cd.change_id = ?
        ORDER BY d.sort_order
    """, (change_id,))
    return jsonify(rows)


@app.route("/api/change/<change_id>/departments", methods=["PUT"])
def api_set_change_depts(change_id):
    """변경사항의 부서 배정 (전체 교체)"""
    data = request.get_json()
    dept_ids = data.get("dept_ids", [])
    conn = get_db()
    now = datetime.now().isoformat()
    conn.execute("DELETE FROM change_department WHERE change_id = ?", (change_id,))
    for did in dept_ids:
        conn.execute(
            "INSERT INTO change_department (change_id, dept_id, created_at) VALUES (?,?,?)",
            (change_id, did, now),
        )
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "change_id": change_id, "count": len(dept_ids)})


# ─── 증빙자료 등록 API ──────────────────────────────────

@app.route("/api/evidence")
def api_evidence_list():
    """증빙자료 목록 (준거 필터 지원)"""
    criterion = request.args.get("criterion", "")
    cycle = request.args.get("cycle", "")
    sql = "SELECT * FROM evidence_registry WHERE 1=1"
    params = []
    if criterion:
        sql += " AND criterion = ?"
        params.append(criterion)
    if cycle:
        sql += " AND cycle = ?"
        params.append(cycle)
    sql += " ORDER BY criterion, ev_id"
    return jsonify(query_all(sql, params))


@app.route("/api/evidence", methods=["POST"])
def api_add_evidence():
    """증빙자료 등록"""
    data = request.get_json()
    required = ["criterion", "doc_title"]
    if not all(data.get(k) for k in required):
        return jsonify({"error": "criterion, doc_title required"}), 400
    conn = get_db()
    now = datetime.now().isoformat()
    cur = conn.execute("""
        INSERT INTO evidence_registry (cycle, criterion, doc_title, doc_number, doc_location, notes, is_reusable, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get("cycle", "3"), data["criterion"], data["doc_title"],
        data.get("doc_number", ""), data.get("doc_location", ""),
        data.get("notes", ""), data.get("is_reusable", 1), now,
    ))
    ev_id = cur.lastrowid
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "ev_id": ev_id})


@app.route("/api/evidence/<int:ev_id>", methods=["PUT"])
def api_update_evidence(ev_id):
    """증빙자료 수정"""
    data = request.get_json()
    conn = get_db()
    conn.execute("""
        UPDATE evidence_registry
        SET doc_title=?, doc_number=?, doc_location=?, notes=?, is_reusable=?, cycle=?
        WHERE ev_id=?
    """, (
        data.get("doc_title", ""), data.get("doc_number", ""),
        data.get("doc_location", ""), data.get("notes", ""),
        data.get("is_reusable", 1), data.get("cycle", "3"), ev_id,
    ))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/evidence/<int:ev_id>", methods=["DELETE"])
def api_delete_evidence(ev_id):
    """증빙자료 삭제"""
    conn = get_db()
    conn.execute("DELETE FROM evidence_registry WHERE ev_id=?", (ev_id,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/evidence/summary")
def api_evidence_summary():
    """준거별 증빙자료 등록 현황"""
    rows = query_all("""
        SELECT criterion, COUNT(*) as total,
               SUM(CASE WHEN cycle='3' THEN 1 ELSE 0 END) as cycle3,
               SUM(CASE WHEN cycle='4' THEN 1 ELSE 0 END) as cycle4,
               SUM(CASE WHEN is_reusable=1 THEN 1 ELSE 0 END) as reusable
        FROM evidence_registry
        GROUP BY criterion ORDER BY criterion
    """)
    return jsonify(rows)


# ─── 증빙자료 관리 페이지 ───────────────────────────────

@app.route("/evidence")
def evidence_page():
    return render_template("evidence.html")


# ─── AI 어시스턴트 API ─────────────────────────────────

@app.route("/api/ai/ask", methods=["POST"])
def api_ai_ask():
    """AI에게 질문 (RAG)"""
    data = request.get_json()
    query = data.get("query", "")
    criterion = data.get("criterion", "")
    context_type = data.get("context_type", "general")
    
    if not query and context_type == "general":
        return jsonify({"error": "질문 내용을 입력하세요"}), 400
        
    result = ask_ai(DB_PATH, query, criterion, context_type)
    
    if "error" in result:
        return jsonify({"error": result["error"]}), result.get("status_code", 500)
        
    return jsonify(result)


# ─── 지식그래프 API ────────────────────────────────────

@app.route("/api/graph/data")
def api_graph_data():
    """지식그래프 시각화 데이터 (vis.js 호환)"""
    conn = get_db()
    
    # 노드 로드 (충분히 크게)
    node_rows = conn.execute("SELECT node_id, node_type, title, label FROM graph_nodes LIMIT 1500").fetchall()
    nodes = []
    
    type_colors = {
        "criterion": "#6366f1",  # indigo
        "section": "#10b981",    # emerald
        "change_atom": "#f59e0b", # amber
        "action": "#ec4899",     # pink
        "department": "#8b5cf6"  # violet
    }
    
    for r in node_rows:
        display_title = r["title"] or r["label"] or r["node_id"]
        nodes.append({
            "id": r["node_id"],
            "label": display_title[:20] + ("..." if len(display_title) > 20 else ""),
            "title": f"[{r['node_type']}] {display_title}",
            "group": r["node_type"],
            "color": type_colors.get(r["node_type"], "#9ca3af")
        })
        
    # 엣지 로드
    node_ids = {n["id"] for n in nodes}
    edge_rows = conn.execute("SELECT source_node_id, target_node_id, edge_type, score FROM graph_edges").fetchall()
    edges = []
    
    for r in edge_rows:
        if r["source_node_id"] in node_ids and r["target_node_id"] in node_ids:
            edges.append({
                "from": r["source_node_id"],
                "to": r["target_node_id"],
                "label": r["edge_type"],
                "value": r["score"],
                "font": {"size": 8, "align": "middle"}
            })
            
    conn.close()
    return jsonify({"nodes": nodes, "edges": edges})

@app.route("/graph")
def graph_page():
    return render_template("graph.html")


# ─── 실행 ──────────────────────────────────────────────

if __name__ == "__main__":
    print(f"📊 대시보드 서버 시작: http://localhost:5000")
    print(f"   DB: {DB_PATH}")
    app.run(debug=True, host="0.0.0.0", port=5000)
