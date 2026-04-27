"""
인증평가 편람 비교분석 대시보드 — Flask 서버
=============================================
SQLite DB에서 데이터를 읽어 JSON API로 제공합니다.
"""

import hashlib
import json
import os
import sys
import sqlite3
import uuid
from functools import wraps
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file

from ai_service import ask_ai
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

DB_PATH = Path(__file__).parent / "accreditation_review.db"
APP_DIR = Path(__file__).parent
UPLOAD_DIR = APP_DIR / "uploads"
ALLOWED_UPLOAD_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "hwp", "hwpx", "zip", "png", "jpg", "jpeg",
}
SUBMISSION_STATUSES = {"not_submitted", "submitted", "revision_requested", "approved"}


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


def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query_one(
        "SELECT user_id, email, display_name, role, department FROM users WHERE user_id=? AND is_active=1",
        (user_id,),
    )


def wants_json_response():
    return request.path.startswith("/api/") or "application/json" in request.headers.get("Accept", "")


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not current_user():
            if wants_json_response():
                return jsonify({"error": "login required"}), 401
            return redirect(url_for("login_page", next=request.path))
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = current_user()
        if not user:
            return jsonify({"error": "login required"}), 401
        if user["role"] != "admin":
            return jsonify({"error": "admin required"}), 403
        return fn(*args, **kwargs)
    return wrapper


def support_departments_match(support_departments, department):
    if not support_departments or not department:
        return False
    parts = [p.strip() for p in support_departments.split(";") if p.strip()]
    return department in parts


def user_can_access_submission(user, submission_row):
    if not user or not submission_row:
        return False
    if user["role"] == "admin":
        return True
    department = user.get("department")
    return (
        department
        and (
            submission_row.get("primary_department") == department
            or support_departments_match(submission_row.get("support_departments"), department)
        )
    )


def get_submission_for_user(conn, submission_id, user):
    row = conn.execute("""
        SELECT
            es.*,
            ec.checklist_id, ec.change_id, ec.cycle4_criterion, ec.cycle4_title,
            ec.section_type, ec.field_or_focus, ec.primary_department,
            ec.support_departments, ec.data_period, ec.metric_or_threshold,
            ec.evidence_link, ec.official_confirmation_needed, ec.preparation_task
        FROM evidence_submission es
        JOIN evidence_checklist ec ON ec.checklist_id = es.checklist_id
        WHERE es.submission_id = ?
    """, (submission_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    return data if user_can_access_submission(user, data) else None


def allowed_upload(filename):
    if "." not in filename:
        return False
    return filename.rsplit(".", 1)[1].lower() in ALLOWED_UPLOAD_EXTENSIONS


def file_sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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

    # 내부 MVP용 사용자 계정
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'department')),
            department TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_department ON users(department)")

    # 체크리스트 항목별 제출 상태
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_submission (
            submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
            checklist_id TEXT NOT NULL UNIQUE,
            assigned_department TEXT,
            status TEXT NOT NULL DEFAULT 'not_submitted',
            last_file_id INTEGER,
            submitted_by_user_id INTEGER,
            submitted_at TEXT,
            reviewed_by_user_id INTEGER,
            reviewer_email TEXT,
            review_note TEXT,
            reviewed_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_es_checklist ON evidence_submission(checklist_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_es_status ON evidence_submission(status)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_es_department ON evidence_submission(assigned_department)")

    # 업로드 파일 버전 이력
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_file (
            file_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            version_no INTEGER NOT NULL,
            original_filename TEXT NOT NULL,
            stored_filename TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            file_hash TEXT NOT NULL,
            uploaded_by_user_id INTEGER NOT NULL,
            uploader_email TEXT NOT NULL,
            uploaded_at TEXT NOT NULL,
            UNIQUE(submission_id, version_no)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ef_submission ON evidence_file(submission_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_ef_hash ON evidence_file(file_hash)")

    # 제출 상태와 업로드 이벤트 로그
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence_submission_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            submission_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT,
            note TEXT,
            actor_user_id INTEGER,
            actor_email TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_eslog_submission ON evidence_submission_log(submission_id)")

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

    # 개발용 로그인 계정. 운영 전 반드시 비밀번호 교체/SSO 전환 필요.
    conn.execute("""
        INSERT OR IGNORE INTO users (email, password_hash, display_name, role, department, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        "admin@local.accreditation",
        generate_password_hash(os.environ.get("ADMIN_SEED_PASSWORD", "admin1234")),
        "평가인증 총괄자",
        "admin",
        None,
        now,
    ))
    for name, code, _cat, _order in seed_depts:
        conn.execute("""
            INSERT OR IGNORE INTO users (email, password_hash, display_name, role, department, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            f"{code.lower()}@local.accreditation",
            generate_password_hash(os.environ.get("DEPT_SEED_PASSWORD", "dept1234")),
            f"{name} 담당자",
            "department",
            name,
            now,
        ))

    # evidence_checklist를 제출 과제로 투영하되 원천 테이블은 수정하지 않는다.
    checklist_exists = conn.execute("""
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type='table' AND name='evidence_checklist'
    """).fetchone()[0]
    if checklist_exists:
        conn.execute("""
            INSERT OR IGNORE INTO evidence_submission (
                checklist_id, assigned_department, status, created_at, updated_at
            )
            SELECT checklist_id, primary_department, 'not_submitted', ?, ?
            FROM evidence_checklist
        """, (now, now))

    conn.commit()
    conn.close()
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

init_extra_tables()


# ─── 페이지 라우트 ──────────────────────────────────────

@app.errorhandler(RequestEntityTooLarge)
def handle_file_too_large(_error):
    return jsonify({"error": "파일은 50MB 이하만 업로드할 수 있습니다"}), 413


@app.route("/login", methods=["GET", "POST"])
def login_page():
    if request.method in {"GET", "HEAD"}:
        if current_user():
            return redirect(url_for("submissions_page"))
        return render_template("login.html")

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""
    next_url = request.args.get("next") or url_for("submissions_page")

    user = query_one("""
        SELECT user_id, email, password_hash, display_name, role, department, is_active
        FROM users
        WHERE email = ?
    """, (email,))

    if not user or not user["is_active"] or not check_password_hash(user["password_hash"], password):
        return render_template("login.html", error="이메일 또는 비밀번호를 확인하세요", email=email), 401

    session.clear()
    session["user_id"] = user["user_id"]
    session["email"] = user["email"]
    session["role"] = user["role"]
    return redirect(next_url)


@app.route("/logout")
def logout_page():
    session.clear()
    return redirect(url_for("login_page"))


@app.route("/submissions")
@login_required
def submissions_page():
    return render_template("submissions.html", user=current_user())


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
            ca.item_path_4, ca.field_name_4, ca.review_reason,
            COALESCE(notes.note_count, 0) AS note_count
        FROM change_atom ca
        LEFT JOIN (
            SELECT change_id, COUNT(*) AS note_count
            FROM review_log
            WHERE TRIM(COALESCE(note, '')) <> ''
            GROUP BY change_id
        ) notes ON notes.change_id = ca.change_id
        WHERE ca.section_type = ?
        ORDER BY ca.cycle4_criterion, ca.change_id
    """, (section,))

    # Group by criterion
    grouped = {}
    for r in rows:
        key = r["cycle4_criterion"]
        if key not in grouped:
            grouped[key] = {"criterion": key, "title": r["cycle4_title"], "note_count": 0, "items": []}
        grouped[key]["note_count"] += r["note_count"]
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


# ─── 제출 포털 API ──────────────────────────────────────

@app.route("/api/me")
@login_required
def api_me():
    return jsonify(current_user())


@app.route("/api/submissions")
@login_required
def api_submissions():
    """증빙 제출 과제 목록"""
    user = current_user()
    status = request.args.get("status", "")
    criterion = request.args.get("criterion", "")
    department = request.args.get("department", "")

    sql = """
        SELECT
            es.submission_id, es.status, es.assigned_department,
            es.submitted_at, es.review_note, es.reviewed_at, es.reviewer_email,
            ec.checklist_id, ec.change_id, ec.cycle4_criterion, ec.cycle4_title,
            ec.section_type, ec.field_or_focus, ec.primary_department,
            ec.support_departments, ec.data_period, ec.metric_or_threshold,
            ec.evidence_link, ec.official_confirmation_needed, ec.preparation_task,
            (
                SELECT COUNT(*)
                FROM evidence_file ef
                WHERE ef.submission_id = es.submission_id
            ) AS file_count,
            (
                SELECT ef.version_no
                FROM evidence_file ef
                WHERE ef.submission_id = es.submission_id
                ORDER BY ef.version_no DESC
                LIMIT 1
            ) AS latest_version_no,
            (
                SELECT ef.original_filename
                FROM evidence_file ef
                WHERE ef.submission_id = es.submission_id
                ORDER BY ef.version_no DESC
                LIMIT 1
            ) AS latest_filename,
            (
                SELECT ef.uploader_email
                FROM evidence_file ef
                WHERE ef.submission_id = es.submission_id
                ORDER BY ef.version_no DESC
                LIMIT 1
            ) AS latest_uploader_email,
            (
                SELECT ef.uploaded_at
                FROM evidence_file ef
                WHERE ef.submission_id = es.submission_id
                ORDER BY ef.version_no DESC
                LIMIT 1
            ) AS latest_uploaded_at
        FROM evidence_submission es
        JOIN evidence_checklist ec ON ec.checklist_id = es.checklist_id
        WHERE 1=1
    """
    params = []

    if user["role"] == "department":
        sql += """
            AND (
                ec.primary_department = ?
                OR (';' || COALESCE(ec.support_departments, '') || ';') LIKE ?
            )
        """
        params.extend([user["department"], f"%;{user['department']};%"])
    elif department:
        sql += " AND ec.primary_department = ?"
        params.append(department)

    if status:
        sql += " AND es.status = ?"
        params.append(status)
    if criterion:
        sql += " AND ec.cycle4_criterion = ?"
        params.append(criterion)

    sql += " ORDER BY ec.cycle4_criterion, ec.primary_department, ec.checklist_id"
    return jsonify(query_all(sql, params))


@app.route("/api/submissions/<int:submission_id>/files")
@login_required
def api_submission_files(submission_id):
    user = current_user()
    conn = get_db()
    submission = get_submission_for_user(conn, submission_id, user)
    if not submission:
        conn.close()
        return jsonify({"error": "not found"}), 404

    rows = conn.execute("""
        SELECT file_id, submission_id, version_no, original_filename, stored_filename,
               file_size, file_hash, uploaded_by_user_id, uploader_email, uploaded_at
        FROM evidence_file
        WHERE submission_id = ?
        ORDER BY version_no DESC
    """, (submission_id,)).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/submissions/<int:submission_id>/upload", methods=["POST"])
@login_required
def api_upload_submission_file(submission_id):
    user = current_user()
    conn = get_db()
    submission = get_submission_for_user(conn, submission_id, user)
    if not submission:
        conn.close()
        return jsonify({"error": "not found"}), 404

    uploaded = request.files.get("file")
    if not uploaded or not uploaded.filename:
        conn.close()
        return jsonify({"error": "file required"}), 400

    raw_filename = uploaded.filename.replace("\\", "/").split("/")[-1]
    if not allowed_upload(raw_filename):
        conn.close()
        return jsonify({"error": "허용되지 않는 파일 형식입니다"}), 400

    ext = raw_filename.rsplit(".", 1)[1].lower()
    display_filename = raw_filename or f"upload.{ext}"
    next_version = conn.execute("""
        SELECT COALESCE(MAX(version_no), 0) + 1
        FROM evidence_file
        WHERE submission_id = ?
    """, (submission_id,)).fetchone()[0]

    stored_filename = f"v{next_version}_{uuid.uuid4().hex}.{ext}"
    upload_dir = UPLOAD_DIR / str(submission_id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    saved_path = upload_dir / stored_filename
    uploaded.save(saved_path)

    file_size = saved_path.stat().st_size
    if file_size <= 0:
        saved_path.unlink(missing_ok=True)
        conn.close()
        return jsonify({"error": "empty file"}), 400

    file_hash = file_sha256(saved_path)
    relative_path = saved_path.relative_to(APP_DIR).as_posix()
    uploaded_at = now_iso()

    try:
        cur = conn.execute("""
            INSERT INTO evidence_file (
                submission_id, version_no, original_filename, stored_filename,
                file_path, file_size, file_hash, uploaded_by_user_id,
                uploader_email, uploaded_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            submission_id, next_version, display_filename, stored_filename,
            relative_path, file_size, file_hash, user["user_id"],
            user["email"], uploaded_at,
        ))
        file_id = cur.lastrowid
        old_status = submission["status"]
        conn.execute("""
            UPDATE evidence_submission
            SET status='submitted',
                last_file_id=?,
                submitted_by_user_id=?,
                submitted_at=?,
                updated_at=?
            WHERE submission_id=?
        """, (file_id, user["user_id"], uploaded_at, uploaded_at, submission_id))
        conn.execute("""
            INSERT INTO evidence_submission_log (
                submission_id, action, old_status, new_status, note,
                actor_user_id, actor_email, created_at
            )
            VALUES (?, 'upload', ?, 'submitted', ?, ?, ?, ?)
        """, (
            submission_id, old_status, f"v{next_version}: {display_filename}",
            user["user_id"], user["email"], uploaded_at,
        ))
        conn.commit()
    except Exception:
        conn.rollback()
        saved_path.unlink(missing_ok=True)
        conn.close()
        raise

    conn.close()
    return jsonify({
        "ok": True,
        "file_id": file_id,
        "submission_id": submission_id,
        "version_no": next_version,
        "uploader_email": user["email"],
        "uploaded_at": uploaded_at,
        "file_hash": file_hash,
    })


@app.route("/api/submissions/<int:submission_id>/status", methods=["PATCH"])
@admin_required
def api_update_submission_status(submission_id):
    user = current_user()
    data = request.get_json(silent=True) or {}
    new_status = data.get("status", "")
    note = (data.get("note") or "").strip()
    if new_status not in SUBMISSION_STATUSES - {"not_submitted", "submitted"}:
        return jsonify({"error": "status must be revision_requested or approved"}), 400

    conn = get_db()
    submission = get_submission_for_user(conn, submission_id, user)
    if not submission:
        conn.close()
        return jsonify({"error": "not found"}), 404

    file_count = conn.execute(
        "SELECT COUNT(*) FROM evidence_file WHERE submission_id=?",
        (submission_id,),
    ).fetchone()[0]
    if new_status == "approved" and file_count == 0:
        conn.close()
        return jsonify({"error": "업로드된 파일이 없는 제출 항목은 승인할 수 없습니다"}), 400

    old_status = submission["status"]
    reviewed_at = now_iso()
    conn.execute("""
        UPDATE evidence_submission
        SET status=?,
            reviewed_by_user_id=?,
            reviewer_email=?,
            review_note=?,
            reviewed_at=?,
            updated_at=?
        WHERE submission_id=?
    """, (
        new_status, user["user_id"], user["email"], note,
        reviewed_at, reviewed_at, submission_id,
    ))
    conn.execute("""
        INSERT INTO evidence_submission_log (
            submission_id, action, old_status, new_status, note,
            actor_user_id, actor_email, created_at
        )
        VALUES (?, 'status_change', ?, ?, ?, ?, ?, ?)
    """, (
        submission_id, old_status, new_status, note,
        user["user_id"], user["email"], reviewed_at,
    ))
    conn.commit()
    conn.close()
    return jsonify({
        "ok": True,
        "submission_id": submission_id,
        "old_status": old_status,
        "new_status": new_status,
        "reviewer_email": user["email"],
        "reviewed_at": reviewed_at,
    })


@app.route("/api/files/<int:file_id>/download")
@login_required
def api_download_file(file_id):
    user = current_user()
    conn = get_db()
    row = conn.execute("""
        SELECT ef.*, es.submission_id
        FROM evidence_file ef
        JOIN evidence_submission es ON es.submission_id = ef.submission_id
        WHERE ef.file_id = ?
    """, (file_id,)).fetchone()
    if not row:
        conn.close()
        return jsonify({"error": "not found"}), 404

    submission = get_submission_for_user(conn, row["submission_id"], user)
    conn.close()
    if not submission:
        return jsonify({"error": "not found"}), 404

    path = APP_DIR / row["file_path"]
    if not path.exists() or not path.is_file():
        return jsonify({"error": "file missing"}), 404
    return send_file(path, as_attachment=True, download_name=row["original_filename"])


@app.route("/api/criteria-progress")
def api_criteria_progress():
    """준거별 검토 진행률"""
    rows = query_all("""
        SELECT
            progress.*,
            COALESCE(notes.note_count, 0) AS note_count,
            COALESCE(notes.note_item_count, 0) AS note_item_count
        FROM v_criterion_review_progress progress
        LEFT JOIN (
            SELECT
                ca.cycle4_criterion,
                COUNT(*) AS note_count,
                COUNT(DISTINCT ca.change_id) AS note_item_count
            FROM change_atom ca
            JOIN review_log rl ON rl.change_id = ca.change_id
            WHERE TRIM(COALESCE(rl.note, '')) <> ''
            GROUP BY ca.cycle4_criterion
        ) notes ON notes.cycle4_criterion = progress.cycle4_criterion
        ORDER BY progress.cycle4_criterion
    """)
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

    sql = """
        SELECT
            detail.*,
            COALESCE(notes.note_count, 0) AS note_count
        FROM v_change_detail detail
        LEFT JOIN (
            SELECT change_id, COUNT(*) AS note_count
            FROM review_log
            WHERE TRIM(COALESCE(note, '')) <> ''
            GROUP BY change_id
        ) notes ON notes.change_id = detail.change_id
        WHERE 1=1
    """
    params = []

    if criterion:
        sql += " AND detail.cycle4_criterion = ?"
        params.append(criterion)
    if section:
        sql += " AND detail.section_type = ?"
        params.append(section)
    if change_type:
        sql += " AND detail.change_type = ?"
        params.append(change_type)
    if status:
        sql += " AND detail.verification_status = ?"
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
