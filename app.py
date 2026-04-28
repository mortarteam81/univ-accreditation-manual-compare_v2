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
import csv
import secrets
from functools import wraps
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse
from flask import Flask, render_template, jsonify, request, session, redirect, url_for, send_file

from ai_service import ask_ai
from composite_matching import (
    Source,
    build_record,
    composite_score,
    ensure_composite_match_tables,
    insert_links,
    insert_records,
    json_dumps,
    load_change_links,
    load_composite_candidates_for_change,
    load_sources,
)
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.security import check_password_hash, generate_password_hash

try:
    from authlib.integrations.flask_client import OAuth
except ImportError:
    OAuth = None

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-only-change-me")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = os.environ.get("SESSION_COOKIE_SECURE", "").lower() in {"1", "true", "yes"}

DB_PATH = Path(__file__).parent / "accreditation_review.db"
APP_DIR = Path(__file__).parent
UPLOAD_DIR = APP_DIR / "uploads"
ALLOWED_UPLOAD_EXTENSIONS = {
    "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx",
    "hwp", "hwpx", "zip", "png", "jpg", "jpeg",
}
SUBMISSION_STATUSES = {"not_submitted", "submitted", "revision_requested", "approved"}
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
DEV_AUTH_ENABLED = os.environ.get("DEV_AUTH_ENABLED", "").lower() in {"1", "true", "yes"}


def oidc_configured():
    return all(
        os.environ.get(key)
        for key in ("OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET", "OIDC_SERVER_METADATA_URL")
    )


oauth = OAuth(app) if OAuth else None
if oauth and oidc_configured():
    oauth.register(
        name="oidc",
        client_id=os.environ["OIDC_CLIENT_ID"],
        client_secret=os.environ["OIDC_CLIENT_SECRET"],
        server_metadata_url=os.environ["OIDC_SERVER_METADATA_URL"],
        client_kwargs={"scope": "openid email profile"},
    )


# ─── DB 헬퍼 ───────────────────────────────────────────

def get_db():
    conn = sqlite3.connect(str(DB_PATH), timeout=15)
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


def normalize_email(value):
    return (value or "").strip().lower()


def is_safe_next_url(value):
    if not value:
        return False
    parsed = urlparse(value)
    return not parsed.scheme and not parsed.netloc and value.startswith("/")


def safe_next_url(value, fallback="/"):
    return value if is_safe_next_url(value) else fallback


def get_csrf_token():
    token = session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def validate_csrf():
    sent = request.headers.get("X-CSRF-Token", "")
    expected = session.get("csrf_token", "")
    return bool(sent and expected and secrets.compare_digest(sent, expected))


def bool_from_env(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def parse_initial_admin_emails():
    raw = os.environ.get("INITIAL_ADMIN_EMAILS", "")
    return [normalize_email(x) for x in raw.replace("\n", ",").split(",") if normalize_email(x)]


def upsert_seed_user(conn, email, display_name="", role="department", department=None, is_active=True):
    email = normalize_email(email)
    if not email:
        return
    now = now_iso()
    role = role if role in {"admin", "department"} else "department"
    dummy_hash = generate_password_hash(secrets.token_urlsafe(24))
    conn.execute("""
        INSERT INTO users (
            email, password_hash, display_name, role, department, is_active,
            auth_provider, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'oidc', ?, ?)
        ON CONFLICT(email) DO UPDATE SET
            display_name=excluded.display_name,
            role=excluded.role,
            department=excluded.department,
            is_active=excluded.is_active,
            auth_provider=COALESCE(users.auth_provider, 'oidc'),
            updated_at=excluded.updated_at
    """, (
        email,
        dummy_hash,
        display_name.strip() or email,
        role,
        department or None,
        1 if is_active else 0,
        now,
        now,
    ))


def seed_users_from_csv(conn):
    path = os.environ.get("AUTH_USER_SEED_PATH")
    if not path:
        return
    seed_path = Path(path).expanduser()
    if not seed_path.exists():
        raise FileNotFoundError(f"AUTH_USER_SEED_PATH not found: {seed_path}")
    with seed_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            upsert_seed_user(
                conn,
                row.get("email"),
                display_name=row.get("display_name") or row.get("name") or "",
                role=row.get("role") or "department",
                department=row.get("department") or None,
                is_active=bool_from_env(row.get("is_active"), default=True),
            )


def current_user():
    user_id = session.get("user_id")
    if not user_id:
        return None
    return query_one(
        """
        SELECT user_id, email, display_name, role, department, auth_provider,
               oidc_subject, last_login_at
        FROM users
        WHERE user_id=? AND is_active=1
        """,
        (user_id,),
    )


def set_login_session(user):
    session.clear()
    session["user_id"] = user["user_id"]
    session["email"] = user["email"]
    session["role"] = user["role"]
    session["csrf_token"] = secrets.token_urlsafe(32)


def audit_context(user=None):
    user = user or current_user() or {}
    return {
        "actor_user_id": user.get("user_id"),
        "actor_email": user.get("email"),
        "actor_role": user.get("role"),
        "actor_department": user.get("department"),
        "ip_address": request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip(),
        "user_agent": request.headers.get("User-Agent", "")[:500],
    }


def user_is_admin(user=None):
    user = user or current_user()
    return bool(user and user.get("role") == "admin")


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


PUBLIC_ENDPOINTS = {
    "static",
    "login_page",
    "oidc_start",
    "oidc_callback",
    "logout_page",
}


@app.context_processor
def inject_auth_context():
    return {
        "csrf_token": get_csrf_token,
        "current_user": current_user,
        "dev_auth_enabled": DEV_AUTH_ENABLED,
        "oidc_enabled": bool(oauth and oidc_configured()),
    }


@app.before_request
def enforce_auth_and_csrf():
    if request.endpoint in PUBLIC_ENDPOINTS or request.path == "/favicon.ico":
        return None

    if request.path.startswith("/static/"):
        return None

    user = current_user()
    if not user:
        if wants_json_response():
            return jsonify({"error": "login required"}), 401
        next_url = safe_next_url(request.full_path.rstrip("?"), "/")
        return redirect(url_for("login_page", next=next_url))

    if request.method in MUTATING_METHODS and request.path.startswith("/api/"):
        if not validate_csrf():
            return jsonify({"error": "invalid csrf token"}), 403

    return None


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


def change_acl_sql(detail_alias="detail"):
    return f"""
        (
            EXISTS (
                SELECT 1
                FROM department_action da_acl
                WHERE da_acl.change_id = {detail_alias}.change_id
                  AND (
                    da_acl.primary_department = ?
                    OR (';' || COALESCE(da_acl.support_departments, '') || ';') LIKE ?
                  )
            )
            OR EXISTS (
                SELECT 1
                FROM change_department cd_acl
                JOIN departments d_acl ON d_acl.dept_id = cd_acl.dept_id
                WHERE cd_acl.change_id = {detail_alias}.change_id
                  AND d_acl.dept_name = ?
            )
        )
    """


def add_change_acl_filter(sql, params, user, detail_alias="detail"):
    if not user or user.get("role") == "admin":
        return sql, params
    department = user.get("department") or ""
    sql += f" AND {change_acl_sql(detail_alias)}"
    params.extend([department, f"%;{department};%", department])
    return sql, params


def user_can_access_change(conn, change_id, user):
    if not user:
        return False
    if user.get("role") == "admin":
        return True
    department = user.get("department") or ""
    if not department:
        return False
    row = conn.execute(f"""
        SELECT 1
        FROM change_atom ca
        WHERE ca.change_id = ?
          AND {change_acl_sql("ca")}
        LIMIT 1
    """, (change_id, department, f"%;{department};%", department)).fetchone()
    return bool(row)


def criterion_acl_sql(alias="ca"):
    return f"""
        EXISTS (
            SELECT 1
            FROM change_atom ca_acl
            WHERE ca_acl.cycle4_criterion = {alias}.cycle4_criterion
              AND {change_acl_sql("ca_acl")}
        )
    """


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

def ensure_column(conn, table, column, definition):
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def table_exists(conn, table):
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    ).fetchone()
    return bool(row)


def ensure_match_candidate_action_tables(conn):
    if table_exists(conn, "global_match_candidate"):
        ensure_column(conn, "global_match_candidate", "review_status", "TEXT DEFAULT 'candidate'")
        ensure_column(conn, "global_match_candidate", "decision_note", "TEXT")
        ensure_column(conn, "global_match_candidate", "reviewed_by_user_id", "INTEGER")
        ensure_column(conn, "global_match_candidate", "reviewed_by_email", "TEXT")
        ensure_column(conn, "global_match_candidate", "reviewed_at", "TEXT")
        ensure_column(conn, "global_match_candidate", "applied_by_user_id", "INTEGER")
        ensure_column(conn, "global_match_candidate", "applied_by_email", "TEXT")
        ensure_column(conn, "global_match_candidate", "applied_at", "TEXT")
        ensure_column(conn, "global_match_candidate", "mapping_applied_by_user_id", "INTEGER")
        ensure_column(conn, "global_match_candidate", "mapping_applied_by_email", "TEXT")
        ensure_column(conn, "global_match_candidate", "mapping_applied_at", "TEXT")
        ensure_column(conn, "global_match_candidate", "promoted_composite_id", "TEXT")

    conn.execute("""
        CREATE TABLE IF NOT EXISTS match_candidate_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_id TEXT NOT NULL,
            action TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT,
            note TEXT,
            related_change_ids TEXT,
            conflict_change_ids TEXT,
            promoted_composite_id TEXT,
            actor_user_id INTEGER,
            actor_email TEXT,
            actor_role TEXT,
            actor_department TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_match_candidate_log_match ON match_candidate_log(match_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_match_candidate_log_created ON match_candidate_log(created_at)")


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
            actor_user_id INTEGER,
            actor_email TEXT,
            actor_role TEXT,
            actor_department TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        )
    """)
    ensure_column(conn, "review_log", "actor_user_id", "INTEGER")
    ensure_column(conn, "review_log", "actor_email", "TEXT")
    ensure_column(conn, "review_log", "actor_role", "TEXT")
    ensure_column(conn, "review_log", "actor_department", "TEXT")
    ensure_column(conn, "review_log", "ip_address", "TEXT")
    ensure_column(conn, "review_log", "user_agent", "TEXT")
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
            oidc_subject TEXT,
            auth_provider TEXT DEFAULT 'oidc',
            last_login_at TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT
        )
    """)
    ensure_column(conn, "users", "oidc_subject", "TEXT")
    ensure_column(conn, "users", "auth_provider", "TEXT DEFAULT 'oidc'")
    ensure_column(conn, "users", "last_login_at", "TEXT")
    ensure_column(conn, "users", "updated_at", "TEXT")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_department ON users(department)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_users_oidc_subject ON users(oidc_subject)")
    ensure_composite_match_tables(conn)
    ensure_match_candidate_action_tables(conn)

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
        INSERT OR IGNORE INTO users (
            email, password_hash, display_name, role, department,
            auth_provider, created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, 'dev', ?, ?)
    """, (
        "admin@local.accreditation",
        generate_password_hash(os.environ.get("ADMIN_SEED_PASSWORD", "admin1234")),
        "평가인증 총괄자",
        "admin",
        None,
        now,
        now,
    ))
    for name, code, _cat, _order in seed_depts:
        conn.execute("""
            INSERT OR IGNORE INTO users (
                email, password_hash, display_name, role, department,
                auth_provider, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, 'dev', ?, ?)
        """, (
            f"{code.lower()}@local.accreditation",
            generate_password_hash(os.environ.get("DEPT_SEED_PASSWORD", "dept1234")),
            f"{name} 담당자",
            "department",
            name,
            now,
            now,
        ))

    for email in parse_initial_admin_emails():
        upsert_seed_user(conn, email, display_name=email, role="admin", department=None, is_active=True)
    seed_users_from_csv(conn)
    conn.execute("UPDATE users SET updated_at = COALESCE(updated_at, created_at)")

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


def render_login_error(message, status=400):
    return render_template(
        "login.html",
        error=message,
        oauth_configured=bool(oauth and oidc_configured()),
        authlib_installed=bool(OAuth),
        dev_auth_enabled=DEV_AUTH_ENABLED,
        next_url=safe_next_url(request.args.get("next"), "/"),
    ), status


def login_user_from_oidc_claims(claims):
    email = normalize_email(claims.get("email"))
    if not email:
        return None, "OIDC 계정 이메일을 확인할 수 없습니다"
    if claims.get("email_verified") is False:
        return None, "이메일 인증이 완료된 Google 계정만 사용할 수 있습니다"

    conn = get_db()
    user = conn.execute("""
        SELECT user_id, email, display_name, role, department, is_active
        FROM users
        WHERE email = ?
    """, (email,)).fetchone()
    if not user:
        conn.close()
        return None, "이 계정은 아직 앱 접근 허용 목록에 없습니다"
    if not user["is_active"]:
        conn.close()
        return None, "비활성화된 계정입니다"

    now = now_iso()
    conn.execute("""
        UPDATE users
        SET oidc_subject = COALESCE(?, oidc_subject),
            auth_provider = 'google',
            last_login_at = ?,
            updated_at = ?
        WHERE user_id = ?
    """, (claims.get("sub"), now, now, user["user_id"]))
    conn.commit()
    refreshed = conn.execute("""
        SELECT user_id, email, display_name, role, department, auth_provider,
               oidc_subject, last_login_at
        FROM users
        WHERE user_id = ?
    """, (user["user_id"],)).fetchone()
    conn.close()
    data = dict(refreshed)
    set_login_session(data)
    return data, None


@app.route("/login", methods=["GET", "POST"])
def login_page():
    next_url = safe_next_url(request.args.get("next"), "/")
    if request.method in {"GET", "HEAD"}:
        if current_user():
            return redirect(next_url)
        return render_template(
            "login.html",
            oauth_configured=bool(oauth and oidc_configured()),
            authlib_installed=bool(OAuth),
            dev_auth_enabled=DEV_AUTH_ENABLED,
            next_url=next_url,
        )

    if not DEV_AUTH_ENABLED:
        return render_login_error("개발용 비밀번호 로그인은 비활성화되어 있습니다", 403)

    email = (request.form.get("email") or "").strip().lower()
    password = request.form.get("password") or ""

    user = query_one("""
        SELECT user_id, email, password_hash, display_name, role, department, is_active,
               auth_provider, oidc_subject, last_login_at
        FROM users
        WHERE email = ?
    """, (email,))

    if not user or not user["is_active"] or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html",
            error="이메일 또는 비밀번호를 확인하세요",
            email=email,
            oauth_configured=bool(oauth and oidc_configured()),
            authlib_installed=bool(OAuth),
            dev_auth_enabled=DEV_AUTH_ENABLED,
            next_url=next_url,
        ), 401

    conn = get_db()
    now = now_iso()
    conn.execute("UPDATE users SET last_login_at=?, updated_at=? WHERE user_id=?", (now, now, user["user_id"]))
    conn.commit()
    conn.close()
    user["last_login_at"] = now
    set_login_session(user)
    return redirect(next_url)


@app.route("/auth/oidc/start")
def oidc_start():
    if not OAuth:
        return render_login_error("Authlib 패키지가 설치되어 있지 않습니다", 500)
    if not oauth or not oidc_configured():
        return render_login_error("OIDC 환경변수 설정이 필요합니다", 500)
    next_url = safe_next_url(request.args.get("next"), "/")
    session["auth_next"] = next_url
    redirect_uri = os.environ.get("OIDC_REDIRECT_URI") or url_for("oidc_callback", _external=True)
    return oauth.oidc.authorize_redirect(redirect_uri)


@app.route("/auth/oidc/callback")
def oidc_callback():
    if not oauth or not oidc_configured():
        return render_login_error("OIDC 환경변수 설정이 필요합니다", 500)
    try:
        token = oauth.oidc.authorize_access_token()
    except Exception:
        return render_login_error("OIDC 로그인 처리 중 오류가 발생했습니다", 401)
    claims = token.get("userinfo") or {}
    if not claims:
        try:
            claims = oauth.oidc.parse_id_token(token)
        except Exception:
            claims = {}
    user, error = login_user_from_oidc_claims(claims)
    if error:
        return render_login_error(error, 403)
    return redirect(safe_next_url(session.pop("auth_next", None), "/"))


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
    user = current_user()

    sql = """
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
    """
    params = [section]
    sql, params = add_change_acl_filter(sql, params, user, detail_alias="ca")
    sql += """
        ORDER BY ca.cycle4_criterion, ca.change_id
    """
    rows = query_all(sql, params)

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
    user = current_user()
    ca_where, ca_params = add_change_acl_filter(" WHERE 1=1", [], user, detail_alias="ca")

    # 총 변경사항 수
    r = query_one("SELECT COUNT(*) as cnt FROM change_atom ca" + ca_where, ca_params)
    stats["total_changes"] = r["cnt"]

    # 검증 상태별
    rows = query_all("""
        SELECT verification_status, COUNT(*) as cnt
        FROM change_atom ca
    """ + ca_where + " GROUP BY verification_status", ca_params)
    stats["verification_counts"] = {r["verification_status"]: r["cnt"] for r in rows}

    # 변경 유형별
    rows = query_all("""
        SELECT change_type, COUNT(*) as cnt
        FROM change_atom ca
    """ + ca_where + " GROUP BY change_type ORDER BY cnt DESC", ca_params)
    stats["change_type_counts"] = {r["change_type"]: r["cnt"] for r in rows}

    # 위험도별 (department_action 기준)
    risk_sql = """
        SELECT da.risk_level, COUNT(*) as cnt
        FROM department_action da
        JOIN change_atom ca ON ca.change_id = da.change_id
    """ + ca_where + " GROUP BY da.risk_level"
    rows = query_all(risk_sql, ca_params)
    stats["risk_counts"] = {r["risk_level"]: r["cnt"] for r in rows}

    # 검토 상태별
    rows = query_all("""
        SELECT human_review_status, COUNT(*) as cnt
        FROM change_atom ca
    """ + ca_where + " GROUP BY human_review_status", ca_params)
    stats["review_status_counts"] = {r["human_review_status"]: r["cnt"] for r in rows}

    # 총 준거 수
    r = query_one("SELECT COUNT(DISTINCT ca.cycle4_criterion) as cnt FROM change_atom ca" + ca_where, ca_params)
    stats["total_criteria"] = r["cnt"]

    # 원문 수
    source_sql = """
        SELECT COUNT(DISTINCT cs.source_id) as cnt
        FROM canonical_source cs
        JOIN change_atom ca ON ca.source_id_3 = cs.source_id OR ca.source_id_4 = cs.source_id
    """ + ca_where
    r = query_one(source_sql, ca_params)
    stats["total_sources"] = r["cnt"]

    # 매핑 수
    mapping_sql = """
        SELECT COUNT(DISTINCT cm.mapping_id) as cnt
        FROM canonical_mapping cm
        JOIN change_atom ca ON ca.cycle4_criterion = cm.cycle4_criterion
    """ + ca_where
    r = query_one(mapping_sql, ca_params)
    stats["total_mappings"] = r["cnt"]

    return jsonify(stats)


# ─── 제출 포털 API ──────────────────────────────────────

@app.route("/api/me")
@login_required
def api_me():
    user = current_user()
    data = dict(user)
    data["csrf_token"] = get_csrf_token()
    return jsonify(data)


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
    user = current_user()
    where_sql, params = add_change_acl_filter("WHERE 1=1", [], user, detail_alias="ca")
    rows = query_all(f"""
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
            SUM(CASE WHEN ca.change_type = '이동후보' THEN 1 ELSE 0 END) AS cnt_moved,
            COALESCE(SUM(notes.note_count), 0) AS note_count,
            SUM(CASE WHEN COALESCE(notes.note_count, 0) > 0 THEN 1 ELSE 0 END) AS note_item_count
        FROM change_atom ca
        LEFT JOIN (
            SELECT change_id, COUNT(*) AS note_count
            FROM review_log
            WHERE TRIM(COALESCE(note, '')) <> ''
            GROUP BY change_id
        ) notes ON notes.change_id = ca.change_id
        {where_sql}
        GROUP BY ca.cycle4_criterion, ca.cycle4_title
        ORDER BY ca.cycle4_criterion
    """, params)
    return jsonify(rows)


@app.route("/api/section-stats")
def api_section_stats():
    """섹션 유형별 변경 통계"""
    user = current_user()
    where_sql, params = add_change_acl_filter("WHERE 1=1", [], user, detail_alias="ca")
    rows = query_all(f"""
        SELECT
            ca.section_type,
            COUNT(*) AS total,
            SUM(CASE WHEN ca.change_type = '유지' THEN 1 ELSE 0 END) AS maintained,
            SUM(CASE WHEN ca.change_type = '변경' THEN 1 ELSE 0 END) AS changed,
            SUM(CASE WHEN ca.change_type = '신설후보' THEN 1 ELSE 0 END) AS new_candidate,
            SUM(CASE WHEN ca.change_type IN ('삭제후보', '삭제/이동후보') THEN 1 ELSE 0 END) AS deleted,
            SUM(CASE WHEN ca.change_type = '이동후보' THEN 1 ELSE 0 END) AS moved
        FROM change_atom ca
        {where_sql}
        GROUP BY ca.section_type
        ORDER BY total DESC
    """, params)
    return jsonify(rows)


@app.route("/api/department-workload")
def api_department_workload():
    """부서별 업무량"""
    user = current_user()
    params = []
    sql = """
        SELECT
            da.primary_department,
            COUNT(*) AS total_actions,
            SUM(CASE WHEN da.risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk,
            SUM(CASE WHEN da.risk_level = 'medium' THEN 1 ELSE 0 END) AS medium_risk,
            SUM(CASE WHEN da.official_confirmation_needed = 1 THEN 1 ELSE 0 END) AS official_needed,
            SUM(CASE WHEN da.notice_required = 1 THEN 1 ELSE 0 END) AS notice_needed
        FROM department_action da
        JOIN change_atom ca ON ca.change_id = da.change_id
        WHERE da.primary_department IS NOT NULL
    """
    if user and user.get("role") == "department":
        department = user.get("department") or ""
        sql += """
            AND (
                da.primary_department = ?
                OR (';' || COALESCE(da.support_departments, '') || ';') LIKE ?
                OR EXISTS (
                    SELECT 1
                    FROM change_department cd_acl
                    JOIN departments d_acl ON d_acl.dept_id = cd_acl.dept_id
                    WHERE cd_acl.change_id = da.change_id
                      AND d_acl.dept_name = ?
                )
            )
        """
        params.extend([department, f"%;{department};%", department])
    sql += " GROUP BY da.primary_department ORDER BY total_actions DESC"
    rows = query_all(sql, params)
    return jsonify(rows)


@app.route("/api/mapping-overview")
def api_mapping_overview():
    """3↔4주기 준거 매핑 현황"""
    user = current_user()
    sql = "SELECT DISTINCT cm.* FROM canonical_mapping cm WHERE 1=1"
    params = []
    if user and user.get("role") == "department":
        department = user.get("department") or ""
        sql += f" AND {criterion_acl_sql('cm')}"
        params.extend([department, f"%;{department};%", department])
    sql += " ORDER BY cm.cycle4_criterion, cm.cycle3_criterion"
    rows = query_all(sql, params)
    return jsonify(rows)


@app.route("/api/criteria-list")
def api_criteria_list():
    """준거 목록 (필터용)"""
    user = current_user()
    sql = """
        SELECT DISTINCT cycle4_criterion, cycle4_title
        FROM change_atom ca
        WHERE 1=1
    """
    params = []
    sql, params = add_change_acl_filter(sql, params, user, detail_alias="ca")
    sql += """
        ORDER BY cycle4_criterion
    """
    rows = query_all(sql, params)
    return jsonify(rows)


def build_change_filters(args, include_status=True):
    """Build shared WHERE clauses for comparison review filters."""
    clauses = ["1=1"]
    params = []

    criterion = args.get("criterion", "")
    section = args.get("section", "")
    change_type = args.get("change_type", "")
    status = args.get("status", "")
    keyword = args.get("q", "").strip()
    has_note = args.get("has_note", "")

    if criterion:
        clauses.append("detail.cycle4_criterion = ?")
        params.append(criterion)
    if section:
        clauses.append("detail.section_type = ?")
        params.append(section)
    if change_type:
        clauses.append("detail.change_type = ?")
        params.append(change_type)
    if include_status and status:
        clauses.append("detail.verification_status = ?")
        params.append(status)
    if keyword:
        like = f"%{keyword}%"
        clauses.append("""
            (
                detail.change_id LIKE ?
                OR detail.cycle4_criterion LIKE ?
                OR detail.cycle4_title LIKE ?
                OR detail.cycle3_criterion LIKE ?
                OR detail.cycle3_title LIKE ?
                OR detail.section_label LIKE ?
                OR detail.source_text_3 LIKE ?
                OR detail.source_text_4 LIKE ?
                OR detail.review_reason LIKE ?
                OR detail.change_categories LIKE ?
                OR risk.primary_departments LIKE ?
            )
        """)
        params.extend([like] * 11)
    if has_note == "1":
        clauses.append("COALESCE(notes.note_count, 0) > 0")

    return " AND ".join(clauses), params


def change_review_base_query():
    """Base SELECT for comparison review rows."""
    return """
        FROM v_change_detail detail
        LEFT JOIN (
            SELECT change_id, COUNT(*) AS note_count
            FROM review_log
            WHERE TRIM(COALESCE(note, '')) <> ''
            GROUP BY change_id
        ) notes ON notes.change_id = detail.change_id
        LEFT JOIN (
            SELECT
                change_id,
                MAX(CASE risk_level
                    WHEN 'high' THEN 3
                    WHEN 'medium' THEN 2
                    WHEN 'low' THEN 1
                    ELSE 0
                END) AS risk_rank,
                SUM(CASE WHEN risk_level = 'high' THEN 1 ELSE 0 END) AS high_risk_count,
                SUM(CASE WHEN risk_level = 'medium' THEN 1 ELSE 0 END) AS medium_risk_count,
                GROUP_CONCAT(DISTINCT primary_department) AS primary_departments
            FROM department_action
            GROUP BY change_id
        ) risk ON risk.change_id = detail.change_id
    """


@app.route("/api/changes")
def api_changes():
    """변경사항 목록 (필터 지원)"""
    where_sql, params = build_change_filters(request.args, include_status=True)
    user = current_user()
    if user and user.get("role") == "department":
        department = user.get("department") or ""
        where_sql += f" AND {change_acl_sql('detail')}"
        params.extend([department, f"%;{department};%", department])
    sort = request.args.get("sort", "priority")
    order_sql = {
        "priority": """
            CASE
                WHEN detail.verification_status = 'candidate' AND COALESCE(risk.risk_rank, 0) >= 3 THEN 0
                WHEN detail.verification_status = 'needs_review' AND COALESCE(risk.risk_rank, 0) >= 3 THEN 1
                WHEN detail.verification_status = 'candidate' THEN 2
                WHEN detail.verification_status = 'needs_review' THEN 3
                WHEN COALESCE(detail.manual_review_required, 0) = 1 THEN 4
                WHEN COALESCE(risk.risk_rank, 0) >= 3 THEN 5
                ELSE 6
            END,
            COALESCE(risk.risk_rank, 0) DESC,
            COALESCE(detail.similarity, 1) ASC,
            detail.cycle4_criterion,
            detail.change_id
        """,
        "high_risk": """
            COALESCE(risk.risk_rank, 0) DESC,
            COALESCE(risk.high_risk_count, 0) DESC,
            CASE detail.verification_status
                WHEN 'candidate' THEN 0
                WHEN 'needs_review' THEN 1
                ELSE 2
            END,
            detail.cycle4_criterion,
            detail.change_id
        """,
        "candidate": """
            CASE detail.verification_status
                WHEN 'candidate' THEN 0
                WHEN 'needs_review' THEN 1
                ELSE 2
            END,
            COALESCE(risk.risk_rank, 0) DESC,
            detail.cycle4_criterion,
            detail.change_id
        """,
        "status": """
            CASE detail.verification_status
                WHEN 'needs_review' THEN 0
                WHEN 'candidate' THEN 1
                WHEN 'deferred' THEN 2
                WHEN 'rejected' THEN 3
                WHEN 'confirmed' THEN 4
                ELSE 5
            END,
            detail.cycle4_criterion,
            detail.change_id
        """,
        "similarity_low": """
            CASE WHEN detail.similarity IS NULL THEN 1 ELSE 0 END,
            detail.similarity ASC,
            COALESCE(risk.risk_rank, 0) DESC,
            detail.cycle4_criterion,
            detail.change_id
        """,
        "criterion": "detail.cycle4_criterion, detail.section_type, detail.change_id",
    }.get(sort, "detail.cycle4_criterion, detail.section_type, detail.change_id")

    sql = """
        SELECT
            detail.*,
            COALESCE(notes.note_count, 0) AS note_count,
            COALESCE(risk.risk_rank, 0) AS risk_rank,
            COALESCE(risk.high_risk_count, 0) AS high_risk_count,
            COALESCE(risk.medium_risk_count, 0) AS medium_risk_count,
            COALESCE(risk.primary_departments, '') AS primary_departments
    """ + change_review_base_query() + f"""
        WHERE {where_sql}
        ORDER BY {order_sql}
    """
    rows = query_all(sql, params)
    return jsonify(rows)


@app.route("/api/change-status-summary")
def api_change_status_summary():
    """상태 메뉴 카운트 (현재 필터 기준, 상태 필터 제외)."""
    where_sql, params = build_change_filters(request.args, include_status=False)
    user = current_user()
    if user and user.get("role") == "department":
        department = user.get("department") or ""
        where_sql += f" AND {change_acl_sql('detail')}"
        params.extend([department, f"%;{department};%", department])
    rows = query_all("""
        SELECT detail.verification_status AS status, COUNT(*) AS cnt
    """ + change_review_base_query() + f"""
        WHERE {where_sql}
        GROUP BY detail.verification_status
    """, params)
    return jsonify({r["status"]: r["cnt"] for r in rows})


def source_preview(conn, source_id):
    if not source_id:
        return None
    row = conn.execute(
        """
        SELECT source_id, cycle, criterion, title, section_type, field_name, content
        FROM canonical_source
        WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()
    if not row:
        return None
    item = dict(row)
    content = item.get("content") or ""
    item["content_preview"] = content[:180] + ("..." if len(content) > 180 else "")
    item.pop("content", None)
    return item


def source_conflict_changes(conn, source_id, exclude_change_id=None):
    if not source_id:
        return []
    rows = conn.execute(
        """
        SELECT change_id, source_id_3, source_id_4, cycle3_criterion, cycle3_title,
               cycle4_criterion, cycle4_title, section_type, change_type,
               similarity, verification_status, source_text_3, source_text_4
        FROM change_atom
        WHERE (source_id_3 = ? OR source_id_4 = ?)
          AND (? IS NULL OR change_id <> ?)
        ORDER BY change_id
        """,
        (source_id, source_id, exclude_change_id, exclude_change_id),
    ).fetchall()
    conflicts = []
    for row in rows:
        item = dict(row)
        for key in ("source_text_3", "source_text_4"):
            text = item.get(key) or ""
            item[f"{key}_preview"] = text[:140] + ("..." if len(text) > 140 else "")
            item.pop(key, None)
        conflicts.append(item)
    return conflicts


def related_change_ids_for_match(conn, row):
    change_ids = {row["change_id"]}
    for source_id in (row["query_source_id"], row["candidate_source_id"]):
        if not source_id:
            continue
        rows = conn.execute(
            """
            SELECT change_id
            FROM change_atom
            WHERE source_id_3 = ? OR source_id_4 = ?
            """,
            (source_id, source_id),
        ).fetchall()
        change_ids.update(item["change_id"] for item in rows)
    return sorted(change_ids)


def load_match_candidates_for_change(conn, change_id, limit=3):
    ensure_match_candidate_action_tables(conn)
    rows = conn.execute(
        """
        SELECT *
        FROM global_match_candidate
        WHERE change_id = ?
          AND rank <= ?
        ORDER BY rank, score DESC, match_id
        """,
        (change_id, limit),
    ).fetchall()
    candidates = []
    for row in rows:
        item = dict(row)
        item["review_status"] = item.get("review_status") or "candidate"
        item["query_source"] = source_preview(conn, item.get("query_source_id"))
        item["candidate_source"] = source_preview(conn, item.get("candidate_source_id"))
        item["conflict_changes"] = source_conflict_changes(
            conn,
            item.get("candidate_source_id"),
            exclude_change_id=change_id,
        )
        item["related_change_ids"] = related_change_ids_for_match(conn, row)
        candidates.append(item)
    return candidates


@app.route("/api/change/<change_id>")
def api_change_detail(change_id):
    """변경사항 상세 + 매칭 후보"""
    user = current_user()
    conn = get_db()
    allowed = user_can_access_change(conn, change_id, user)
    conn.close()
    if not allowed:
        return jsonify({"error": "not found"}), 404

    change = query_one(
        "SELECT * FROM v_change_detail WHERE change_id = ?",
        (change_id,),
    )
    if not change:
        return jsonify({"error": "not found"}), 404

    conn = get_db()
    candidates = load_match_candidates_for_change(conn, change_id)
    composite_candidates = load_composite_candidates_for_change(conn, change_id)
    conn.close()

    # 관련 부서 조치사항
    actions = query_all(
        "SELECT * FROM department_action WHERE change_id = ?",
        (change_id,),
    )

    return jsonify({
        "change": change,
        "match_candidates": candidates,
        "composite_candidates": composite_candidates,
        "department_actions": actions,
    })


@app.route("/api/risk-heatmap")
def api_risk_heatmap():
    """준거×섹션 위험도 히트맵 데이터"""
    user = current_user()
    where_sql, params = add_change_acl_filter("WHERE 1=1", [], user, detail_alias="ca")
    rows = query_all(f"""
        SELECT
            da.cycle4_criterion,
            da.section_type,
            COUNT(*) as total,
            SUM(CASE WHEN da.risk_level = 'high' THEN 1 ELSE 0 END) as high_cnt,
            SUM(CASE WHEN da.risk_level = 'medium' THEN 1 ELSE 0 END) as medium_cnt
        FROM department_action da
        JOIN change_atom ca ON ca.change_id = da.change_id
        {where_sql}
        GROUP BY da.cycle4_criterion, da.section_type
        ORDER BY da.cycle4_criterion, da.section_type
    """, params)
    return jsonify(rows)


# ─── 검토 워크플로우 API ─────────────────────────────────

CHANGE_REVIEW_STATUS_MAP = {
    "confirmed": "approved",
    "rejected": "rejected",
    "needs_review": "pending",
    "deferred": "deferred",
}

COMPOSITE_REVIEW_STATUSES = {"candidate", "approved", "rejected", "needs_review"}
MATCH_CANDIDATE_REVIEW_STATUSES = {"candidate", "approved", "rejected", "needs_review"}


def match_candidate_audit_log(
    conn,
    match_id,
    action,
    old_status,
    new_status,
    note,
    related_change_ids,
    conflict_change_ids,
    user,
    promoted_composite_id=None,
):
    audit = audit_context(user)
    conn.execute("""
        INSERT INTO match_candidate_log (
            match_id, action, old_status, new_status, note, related_change_ids,
            conflict_change_ids, promoted_composite_id,
            actor_user_id, actor_email, actor_role, actor_department,
            ip_address, user_agent, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        match_id,
        action,
        old_status,
        new_status,
        note,
        json_dumps(related_change_ids or []),
        json_dumps(conflict_change_ids or []),
        promoted_composite_id,
        audit["actor_user_id"],
        audit["actor_email"],
        audit["actor_role"],
        audit["actor_department"],
        audit["ip_address"],
        audit["user_agent"],
        now_iso(),
    ))


def get_match_candidate_row(conn, match_id):
    ensure_match_candidate_action_tables(conn)
    return conn.execute(
        "SELECT * FROM global_match_candidate WHERE match_id = ?",
        (match_id,),
    ).fetchone()


def match_candidate_note(row, action_note="", conflict_change_ids=None):
    query = row["query_source_id"] or "-"
    candidate = row["candidate_source_id"] or "-"
    score = row["score"] if row["score"] is not None else 0
    reason = row["match_reason"] or ""
    conflict_label = ", ".join(conflict_change_ids or []) or "없음"
    note = (
        f"[AI 매칭 후보 반영] 후보 {row['match_id']}를 교체 검토 대상으로 등록했습니다. "
        f"기준 원문 {query}, 후보 원문 {candidate}, 점수 {float(score):.3f}. "
        f"충돌 가능 항목: {conflict_label}. {reason}"
    )
    action_note = (action_note or "").strip()
    return f"{note} 관리자 의견: {action_note}" if action_note else note


def canonical_source_row(conn, source_id):
    if not source_id:
        return None
    row = conn.execute(
        """
        SELECT source_id, cycle, criterion, title, section_type, section_label,
               field_name, item_path, content
        FROM canonical_source
        WHERE source_id = ?
        """,
        (source_id,),
    ).fetchone()
    return row


def change_pair_label(row):
    if not row:
        return "- ↔ -"
    return f"{row['source_id_3'] or '-'} ↔ {row['source_id_4'] or '-'}"


def match_change_type(source3, source4, similarity):
    if source3 and source4:
        return "유지" if similarity is not None and float(similarity) >= 0.98 else "변경"
    if source4:
        return "신설후보"
    if source3:
        return "삭제/이동후보"
    return "변경"


def match_similarity(row):
    if row["difflib_similarity"] is not None:
        return float(row["difflib_similarity"])
    if row["score"] is not None:
        return float(row["score"])
    return None


def source_update_tuple(source3, source4, similarity):
    return (
        source3["source_id"] if source3 else None,
        source3["content"] if source3 else None,
        source3["criterion"] if source3 else None,
        source3["title"] if source3 else None,
        source4["source_id"] if source4 else None,
        source4["content"] if source4 else None,
        source4["criterion"] if source4 else None,
        source4["title"] if source4 else None,
        source4["field_name"] if source4 else None,
        source4["item_path"] if source4 else None,
        (source4 or source3)["section_type"] if (source4 or source3) else None,
        (source4 or source3)["section_label"] if (source4 or source3) else None,
        similarity,
        match_change_type(source3, source4, similarity),
    )


def candidate_target_change(conn, row, query):
    target = conn.execute(
        "SELECT * FROM change_atom WHERE change_id = ?",
        (row["change_id"],),
    ).fetchone()
    if target:
        return target
    side_column = "source_id_4" if str(query["cycle"]) == "4" else "source_id_3"
    return conn.execute(
        f"SELECT * FROM change_atom WHERE {side_column} = ? ORDER BY change_id LIMIT 1",
        (query["source_id"],),
    ).fetchone()


def write_match_review_log(conn, change_id, action, old_status, new_status, note, user, now):
    audit = audit_context(user)
    conn.execute("""
        INSERT INTO review_log (
            change_id, action, old_status, new_status, note, reviewer,
            actor_user_id, actor_email, actor_role, actor_department,
            ip_address, user_agent, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        change_id,
        action,
        old_status,
        new_status,
        note,
        audit["actor_email"],
        audit["actor_user_id"],
        audit["actor_email"],
        audit["actor_role"],
        audit["actor_department"],
        audit["ip_address"],
        audit["user_agent"],
        now,
    ))


def apply_match_candidate_mapping(conn, row, user, note):
    """AI 후보를 실제 change_atom 1:1 비교쌍에 반영한다."""
    query = canonical_source_row(conn, row["query_source_id"])
    candidate = canonical_source_row(conn, row["candidate_source_id"])
    if not query or not candidate:
        return None, "source not found"
    if str(query["cycle"]) == str(candidate["cycle"]):
        return None, "candidate must connect different cycles"

    target = candidate_target_change(conn, row, query)
    if not target:
        return None, "target change not found"

    query_cycle = str(query["cycle"])
    candidate_cycle = str(candidate["cycle"])
    if query_cycle == "4" and candidate_cycle == "3":
        source3, source4 = candidate, query
        detach_column = "source_id_3"
        detach_side = "3"
    elif query_cycle == "3" and candidate_cycle == "4":
        source3, source4 = query, candidate
        detach_column = "source_id_4"
        detach_side = "4"
    else:
        return None, "unsupported candidate direction"

    now = now_iso()
    similarity = match_similarity(row)
    old_target_pair = change_pair_label(target)
    new_target_pair = f"{source3['source_id']} ↔ {source4['source_id']}"
    new_status = "needs_review"
    review_reason = (
        f"AI 후보 실제 매칭 적용({row['match_id']}): "
        f"{old_target_pair} -> {new_target_pair}"
    )
    update_values = source_update_tuple(source3, source4, similarity) + (
        new_status,
        CHANGE_REVIEW_STATUS_MAP[new_status],
        review_reason,
        target["change_id"],
    )
    conn.execute("""
        UPDATE change_atom
        SET source_id_3 = ?,
            source_text_3 = ?,
            cycle3_criterion = ?,
            cycle3_title = ?,
            source_id_4 = ?,
            source_text_4 = ?,
            cycle4_criterion = ?,
            cycle4_title = ?,
            field_name_4 = ?,
            item_path_4 = ?,
            section_type = ?,
            section_label = ?,
            similarity = ?,
            change_type = ?,
            verification_status = ?,
            human_review_status = ?,
            manual_review_required = 1,
            review_reason = ?,
            global_match_status = 'strong_candidate'
        WHERE change_id = ?
    """, update_values)

    sim_label = f"{similarity:.3f}" if similarity is not None else "-"
    target_note = (
        f"[AI 매칭 실제 적용] 후보 {row['match_id']}를 실제 비교쌍으로 반영했습니다. "
        f"기존 매칭 {old_target_pair}, 신규 매칭 {new_target_pair}, "
        f"유사도 {sim_label}. "
        f"관리자 의견: {note or '없음'}"
    )
    write_match_review_log(
        conn,
        target["change_id"],
        "ai_match_candidate",
        target["verification_status"],
        new_status,
        target_note,
        user,
        now,
    )

    detached = []
    conflict_rows = conn.execute(
        f"""
        SELECT *
        FROM change_atom
        WHERE {detach_column} = ?
          AND change_id <> ?
        ORDER BY change_id
        """,
        (candidate["source_id"], target["change_id"]),
    ).fetchall()
    for conflict in conflict_rows:
        old_pair = change_pair_label(conflict)
        if detach_side == "3":
            remaining3 = None
            remaining4 = canonical_source_row(conn, conflict["source_id_4"]) if conflict["source_id_4"] else None
        else:
            remaining3 = canonical_source_row(conn, conflict["source_id_3"]) if conflict["source_id_3"] else None
            remaining4 = None
        conflict_values = source_update_tuple(remaining3, remaining4, None) + (
            new_status,
            CHANGE_REVIEW_STATUS_MAP[new_status],
            (
                f"AI 후보 실제 매칭 적용({row['match_id']})으로 "
                f"{candidate['source_id']}를 {target['change_id']}에 재배정했습니다."
            ),
            conflict["change_id"],
        )
        conn.execute("""
            UPDATE change_atom
            SET source_id_3 = ?,
                source_text_3 = ?,
                cycle3_criterion = ?,
                cycle3_title = ?,
                source_id_4 = ?,
                source_text_4 = ?,
                cycle4_criterion = ?,
                cycle4_title = ?,
                field_name_4 = ?,
                item_path_4 = ?,
                section_type = ?,
                section_label = ?,
                similarity = ?,
                change_type = ?,
                verification_status = ?,
                human_review_status = ?,
                manual_review_required = 1,
                review_reason = ?,
                global_match_status = 'possible_candidate'
            WHERE change_id = ?
        """, conflict_values)
        new_pair = (
            f"{remaining3['source_id'] if remaining3 else '-'} ↔ "
            f"{remaining4['source_id'] if remaining4 else '-'}"
        )
        detach_note = (
            f"[AI 매칭 실제 적용] 후보 {row['match_id']} 적용으로 중복 매칭을 정리했습니다. "
            f"기존 매칭 {old_pair}, 조정 후 {new_pair}. "
            f"{candidate['source_id']}는 {target['change_id']}에 재배정되었습니다."
        )
        write_match_review_log(
            conn,
            conflict["change_id"],
            "ai_match_candidate",
            conflict["verification_status"],
            new_status,
            detach_note,
            user,
            now,
        )
        detached.append({
            "change_id": conflict["change_id"],
            "old_pair": old_pair,
            "new_pair": new_pair,
        })

    conn.execute("""
        UPDATE global_match_candidate
        SET applied_by_user_id = COALESCE(applied_by_user_id, ?),
            applied_by_email = COALESCE(applied_by_email, ?),
            applied_at = COALESCE(applied_at, ?),
            mapping_applied_by_user_id = ?,
            mapping_applied_by_email = ?,
            mapping_applied_at = ?
        WHERE match_id = ?
    """, (
        user["user_id"],
        user["email"],
        now,
        user["user_id"],
        user["email"],
        now,
        row["match_id"],
    ))
    return {
        "change_id": target["change_id"],
        "old_pair": old_target_pair,
        "new_pair": new_target_pair,
        "similarity": similarity,
        "detached": detached,
    }, None


def source_ids_for_match_candidate_composite(conn, row):
    sources = load_sources(conn)
    query = sources.get(row["query_source_id"])
    candidate = sources.get(row["candidate_source_id"])
    if not query or not candidate:
        return None, None, "source not found"
    if query.cycle == candidate.cycle:
        return None, None, "candidate must connect different cycles"
    if query.section_type != candidate.section_type:
        return None, None, "candidate must use the same section type"
    if query.field_name and candidate.field_name and query.field_name != candidate.field_name:
        return None, None, "candidate must use the same field"

    conflict_rows = conn.execute(
        """
        SELECT change_id, source_id_3, source_id_4
        FROM change_atom
        WHERE (source_id_3 = ? OR source_id_4 = ?)
          AND change_id <> ?
        """,
        (candidate.source_id, candidate.source_id, row["change_id"]),
    ).fetchall()
    opposite_ids = {query.source_id}
    for conflict in conflict_rows:
        if candidate.cycle == "3" and conflict["source_id_4"]:
            opposite_ids.add(conflict["source_id_4"])
        elif candidate.cycle == "4" and conflict["source_id_3"]:
            opposite_ids.add(conflict["source_id_3"])
    if len(opposite_ids) < 2:
        return None, None, "no conflicting paired source to promote"

    if candidate.cycle == "3":
        direction = "one_to_many"
        query_sources = [candidate]
        candidate_sources = sorted(
            [sources[source_id] for source_id in opposite_ids if source_id in sources],
            key=lambda source: source.source_id,
        )
    else:
        direction = "many_to_one"
        query_sources = [candidate]
        candidate_sources = sorted(
            [sources[source_id] for source_id in opposite_ids if source_id in sources],
            key=lambda source: source.source_id,
        )
    return direction, (query_sources, candidate_sources), ""


def edge_lookup_from_global_candidates(conn):
    rows = conn.execute(
        """
        SELECT query_source_id, candidate_source_id, score
        FROM global_match_candidate
        WHERE query_source_id IS NOT NULL
          AND candidate_source_id IS NOT NULL
        """
    ).fetchall()
    return {
        (row["query_source_id"], row["candidate_source_id"]): float(row["score"] or 0)
        for row in rows
    }


def composite_audit_log(conn, composite_id, action, old_status, new_status, note, related_change_ids, user):
    audit = audit_context(user)
    conn.execute("""
        INSERT INTO composite_match_log (
            composite_id, action, old_status, new_status, note, related_change_ids,
            actor_user_id, actor_email, actor_role, actor_department,
            ip_address, user_agent, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        composite_id,
        action,
        old_status,
        new_status,
        note,
        json_dumps(related_change_ids or []),
        audit["actor_user_id"],
        audit["actor_email"],
        audit["actor_role"],
        audit["actor_department"],
        audit["ip_address"],
        audit["user_agent"],
        now_iso(),
    ))


def get_composite_row(conn, composite_id):
    return conn.execute(
        "SELECT * FROM composite_match_candidate WHERE composite_id = ?",
        (composite_id,),
    ).fetchone()


def get_composite_change_ids(conn, composite_id):
    rows = conn.execute(
        """
        SELECT DISTINCT change_id
        FROM composite_match_link
        WHERE composite_id = ?
        ORDER BY change_id
        """,
        (composite_id,),
    ).fetchall()
    return [row["change_id"] for row in rows]


def composite_status_note(row, action_note=""):
    label = {
        "many_to_one": "통합/재구성",
        "one_to_many": "분리/재배치",
        "many_to_many": "복수 준거 재구성",
    }.get(row["direction"], "복합 매칭")
    note = (
        f"[복합 매칭 반영] {label} 후보 {row['composite_id']}가 승인되어 "
        f"관련 항목을 2차 검수 대상으로 정리했습니다. {row['evidence_reason'] or ''}"
    )
    action_note = (action_note or "").strip()
    return f"{note} 관리자 의견: {action_note}" if action_note else note


@app.route("/api/match-candidate/<match_id>/review", methods=["PATCH"])
@admin_required
def api_review_match_candidate(match_id):
    """AI 1:1 매칭 후보 승인/반려/재검토 상태를 저장한다."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    new_status = (data.get("review_status") or "").strip()
    note = (data.get("note") or "").strip()
    if new_status not in MATCH_CANDIDATE_REVIEW_STATUSES:
        return jsonify({"error": "invalid match candidate review status"}), 400

    conn = get_db()
    row = get_match_candidate_row(conn, match_id)
    if not row:
        conn.close()
        return jsonify({"error": "match candidate not found"}), 404
    old_status = row["review_status"] or "candidate"
    related_change_ids = related_change_ids_for_match(conn, row)
    conflict_change_ids = [
        item["change_id"]
        for item in source_conflict_changes(conn, row["candidate_source_id"], row["change_id"])
    ]
    now = now_iso()
    conn.execute("""
        UPDATE global_match_candidate
        SET review_status = ?,
            decision_note = ?,
            reviewed_by_user_id = ?,
            reviewed_by_email = ?,
            reviewed_at = ?
        WHERE match_id = ?
    """, (new_status, note, user["user_id"], user["email"], now, match_id))
    match_candidate_audit_log(
        conn,
        match_id,
        "review_status_change",
        old_status,
        new_status,
        note,
        related_change_ids,
        conflict_change_ids,
        user,
    )
    conn.commit()
    conn.close()
    return jsonify({
        "ok": True,
        "match_id": match_id,
        "old_status": old_status,
        "new_status": new_status,
        "related_change_ids": related_change_ids,
        "conflict_change_ids": conflict_change_ids,
    })


@app.route("/api/match-candidate/<match_id>/apply", methods=["POST"])
@admin_required
def api_apply_match_candidate(match_id):
    """승인된 AI 후보를 실제 change_atom 비교쌍에 반영한다."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()

    conn = get_db()
    row = get_match_candidate_row(conn, match_id)
    if not row:
        conn.close()
        return jsonify({"error": "match candidate not found"}), 404
    if row["review_status"] != "approved":
        conn.close()
        return jsonify({"error": "approve match candidate before applying"}), 400
    if row["mapping_applied_at"]:
        related_change_ids = related_change_ids_for_match(conn, row)
        conn.close()
        return jsonify({
            "ok": True,
            "match_id": match_id,
            "already_applied": True,
            "changed": [],
            "noted": [],
            "mapping": None,
            "related_change_ids": related_change_ids,
        })

    related_change_ids = related_change_ids_for_match(conn, row)
    conflict_change_ids = [
            item["change_id"]
            for item in source_conflict_changes(conn, row["candidate_source_id"], row["change_id"])
    ]
    mapping, error = apply_match_candidate_mapping(conn, row, user, note)
    if error:
        conn.close()
        return jsonify({"error": error}), 400

    match_candidate_audit_log(
        conn,
        match_id,
        "apply_mapping",
        row["review_status"],
        row["review_status"],
        match_candidate_note(row, note, conflict_change_ids),
        related_change_ids,
        conflict_change_ids,
        user,
    )
    conn.commit()
    conn.close()
    return jsonify({
        "ok": True,
        "match_id": match_id,
        "changed": [mapping] if mapping else [],
        "noted": [],
        "mapping": mapping,
        "related_change_ids": related_change_ids,
        "conflict_change_ids": conflict_change_ids,
    })


@app.route("/api/match-candidate/<match_id>/promote-composite", methods=["POST"])
@admin_required
def api_promote_match_candidate_to_composite(match_id):
    """AI 1:1 후보와 충돌 항목을 복합 매칭 후보로 승격한다."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()
    conn = get_db()
    row = get_match_candidate_row(conn, match_id)
    if not row:
        conn.close()
        return jsonify({"error": "match candidate not found"}), 404
    if row["promoted_composite_id"]:
        conn.close()
        return jsonify({
            "ok": True,
            "match_id": match_id,
            "already_promoted": True,
            "composite_id": row["promoted_composite_id"],
        })

    direction, source_pair, error = source_ids_for_match_candidate_composite(conn, row)
    if error:
        conn.close()
        return jsonify({"error": error}), 400
    query_sources, candidate_sources = source_pair
    source_to_changes, _change_to_sources = load_change_links(conn)
    metrics = composite_score(query_sources, candidate_sources, edge_lookup_from_global_candidates(conn))
    record = build_record(
        direction,
        query_sources,
        candidate_sources,
        metrics,
        source_to_changes,
        "AI 후보 승격 복합 후보",
    )
    existing = conn.execute(
        "SELECT composite_id FROM composite_match_candidate WHERE composite_id = ?",
        (record["composite_id"],),
    ).fetchone()
    if not existing:
        insert_records(conn, [record])
        insert_links(conn, [record], source_to_changes)

    related_change_ids = related_change_ids_for_match(conn, row)
    conflict_change_ids = [
        item["change_id"]
        for item in source_conflict_changes(conn, row["candidate_source_id"], row["change_id"])
    ]
    now = now_iso()
    conn.execute("""
        UPDATE global_match_candidate
        SET promoted_composite_id = ?
        WHERE match_id = ?
    """, (record["composite_id"], match_id))
    composite_audit_log(
        conn,
        record["composite_id"],
        "promoted_from_ai_candidate",
        None,
        "candidate",
        note,
        sorted(set(related_change_ids) | set(conflict_change_ids)),
        user,
    )
    match_candidate_audit_log(
        conn,
        match_id,
        "promote_composite",
        row["review_status"] or "candidate",
        row["review_status"] or "candidate",
        note,
        related_change_ids,
        conflict_change_ids,
        user,
        promoted_composite_id=record["composite_id"],
    )
    conn.commit()
    conn.close()
    return jsonify({
        "ok": True,
        "match_id": match_id,
        "composite_id": record["composite_id"],
        "already_promoted": bool(existing),
        "related_change_ids": related_change_ids,
        "conflict_change_ids": conflict_change_ids,
    })


@app.route("/api/change/<change_id>/status", methods=["PATCH"])
@admin_required
def api_update_status(change_id):
    """변경사항의 검토 상태를 업데이트"""
    user = current_user()
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")  # confirmed / needs_review / rejected
    note = data.get("note", "")

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
    if not user_can_access_change(conn, change_id, user):
        conn.close()
        return jsonify({"error": "change not found"}), 404

    old_status = row["verification_status"]
    now = datetime.now().isoformat()
    audit = audit_context(user)

    # 상태 업데이트
    conn.execute("""
        UPDATE change_atom
        SET verification_status = ?,
            human_review_status = ?
        WHERE change_id = ?
    """, (new_status, CHANGE_REVIEW_STATUS_MAP[new_status], change_id))

    # 로그 기록
    log_cursor = conn.execute("""
        INSERT INTO review_log (
            change_id, action, old_status, new_status, note, reviewer,
            actor_user_id, actor_email, actor_role, actor_department,
            ip_address, user_agent, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        change_id, "status_change", old_status, new_status, note, audit["actor_email"],
        audit["actor_user_id"], audit["actor_email"], audit["actor_role"], audit["actor_department"],
        audit["ip_address"], audit["user_agent"], now,
    ))

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


@app.route("/api/composite/<composite_id>/review", methods=["PATCH"])
@admin_required
def api_review_composite(composite_id):
    """복합 매칭 후보 승인/반려/재검토 상태를 저장한다."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    new_status = (data.get("review_status") or "").strip()
    note = (data.get("note") or "").strip()
    if new_status not in COMPOSITE_REVIEW_STATUSES:
        return jsonify({"error": "invalid composite review status"}), 400

    conn = get_db()
    row = get_composite_row(conn, composite_id)
    if not row:
        conn.close()
        return jsonify({"error": "composite candidate not found"}), 404

    old_status = row["review_status"] or "candidate"
    related_change_ids = get_composite_change_ids(conn, composite_id)
    now = now_iso()
    conn.execute("""
        UPDATE composite_match_candidate
        SET review_status = ?,
            decision_note = ?,
            reviewed_by_user_id = ?,
            reviewed_by_email = ?,
            reviewed_at = ?
        WHERE composite_id = ?
    """, (new_status, note, user["user_id"], user["email"], now, composite_id))
    composite_audit_log(
        conn,
        composite_id,
        "review_status_change",
        old_status,
        new_status,
        note,
        related_change_ids,
        user,
    )
    conn.commit()
    conn.close()
    return jsonify({
        "ok": True,
        "composite_id": composite_id,
        "old_status": old_status,
        "new_status": new_status,
        "related_change_ids": related_change_ids,
    })


@app.route("/api/composite/<composite_id>/apply", methods=["POST"])
@admin_required
def api_apply_composite(composite_id):
    """승인된 복합 후보를 관련 change 항목의 2차 검수 큐와 메모에 반영한다."""
    user = current_user()
    data = request.get_json(silent=True) or {}
    note = (data.get("note") or "").strip()

    conn = get_db()
    row = get_composite_row(conn, composite_id)
    if not row:
        conn.close()
        return jsonify({"error": "composite candidate not found"}), 404
    if row["review_status"] != "approved":
        conn.close()
        return jsonify({"error": "approve composite candidate before applying"}), 400

    related_change_ids = get_composite_change_ids(conn, composite_id)
    if not related_change_ids:
        conn.close()
        return jsonify({"error": "no related changes"}), 400
    if row["applied_at"]:
        conn.close()
        return jsonify({
            "ok": True,
            "composite_id": composite_id,
            "already_applied": True,
            "changed": [],
            "noted": [],
            "related_change_ids": related_change_ids,
        })

    now = now_iso()
    audit = audit_context(user)
    applied_note = composite_status_note(row, note)
    changed = []
    noted = []
    for change_id in related_change_ids:
        current = conn.execute(
            "SELECT verification_status FROM change_atom WHERE change_id = ?",
            (change_id,),
        ).fetchone()
        if not current:
            continue
        old_status = current["verification_status"]
        if old_status in {"candidate", "deferred"}:
            new_status = "needs_review"
            conn.execute("""
                UPDATE change_atom
                SET verification_status = ?,
                    human_review_status = ?
                WHERE change_id = ?
            """, (new_status, CHANGE_REVIEW_STATUS_MAP[new_status], change_id))
            conn.execute("""
                INSERT INTO review_log (
                    change_id, action, old_status, new_status, note, reviewer,
                    actor_user_id, actor_email, actor_role, actor_department,
                    ip_address, user_agent, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                change_id,
                "status_change",
                old_status,
                new_status,
                applied_note,
                audit["actor_email"],
                audit["actor_user_id"],
                audit["actor_email"],
                audit["actor_role"],
                audit["actor_department"],
                audit["ip_address"],
                audit["user_agent"],
                now,
            ))
            changed.append({"change_id": change_id, "old_status": old_status, "new_status": new_status})
        else:
            conn.execute("""
                INSERT INTO review_log (
                    change_id, action, note, reviewer,
                    actor_user_id, actor_email, actor_role, actor_department,
                    ip_address, user_agent, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                change_id,
                "composite_match",
                applied_note,
                audit["actor_email"],
                audit["actor_user_id"],
                audit["actor_email"],
                audit["actor_role"],
                audit["actor_department"],
                audit["ip_address"],
                audit["user_agent"],
                now,
            ))
            noted.append({"change_id": change_id, "status": old_status})

    conn.execute("""
        UPDATE composite_match_candidate
        SET applied_by_user_id = ?,
            applied_by_email = ?,
            applied_at = ?
        WHERE composite_id = ?
    """, (user["user_id"], user["email"], now, composite_id))
    composite_audit_log(
        conn,
        composite_id,
        "apply_to_changes",
        row["review_status"],
        row["review_status"],
        note,
        related_change_ids,
        user,
    )
    conn.commit()
    conn.close()
    return jsonify({
        "ok": True,
        "composite_id": composite_id,
        "changed": changed,
        "noted": noted,
        "related_change_ids": related_change_ids,
    })


@app.route("/api/change/<change_id>/note", methods=["POST"])
def api_add_note(change_id):
    """변경사항에 검토 메모를 추가"""
    user = current_user()
    data = request.get_json()
    note = data.get("note", "").strip()

    if not note:
        return jsonify({"error": "note is empty"}), 400

    conn = get_db()
    if not user_can_access_change(conn, change_id, user):
        conn.close()
        return jsonify({"error": "change not found"}), 404
    now = datetime.now().isoformat()
    audit = audit_context(user)
    action = "note" if user["role"] == "admin" else "department_note"

    conn.execute("""
        INSERT INTO review_log (
            change_id, action, note, reviewer,
            actor_user_id, actor_email, actor_role, actor_department,
            ip_address, user_agent, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        change_id, action, note, audit["actor_email"],
        audit["actor_user_id"], audit["actor_email"], audit["actor_role"], audit["actor_department"],
        audit["ip_address"], audit["user_agent"], now,
    ))

    conn.commit()
    conn.close()

    return jsonify({"ok": True, "change_id": change_id})


@app.route("/api/change/<change_id>/history")
def api_change_history(change_id):
    """변경사항의 검토 이력"""
    user = current_user()
    conn = get_db()
    allowed = user_can_access_change(conn, change_id, user)
    conn.close()
    if not allowed:
        return jsonify({"error": "not found"}), 404
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
@admin_required
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
    user = current_user()
    conn = get_db()
    allowed = user_can_access_change(conn, change_id, user)
    conn.close()
    if not allowed:
        return jsonify({"error": "not found"}), 404
    rows = query_all("""
        SELECT cd.*, d.dept_name, d.dept_code, d.category
        FROM change_department cd
        JOIN departments d ON cd.dept_id = d.dept_id
        WHERE cd.change_id = ?
        ORDER BY d.sort_order
    """, (change_id,))
    return jsonify(rows)


@app.route("/api/change/<change_id>/departments", methods=["PUT"])
@admin_required
def api_set_change_depts(change_id):
    """변경사항의 부서 배정 (전체 교체)"""
    user = current_user()
    data = request.get_json()
    dept_ids = data.get("dept_ids", [])
    conn = get_db()
    if not user_can_access_change(conn, change_id, user):
        conn.close()
        return jsonify({"error": "not found"}), 404
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
    user = current_user()
    criterion = request.args.get("criterion", "")
    cycle = request.args.get("cycle", "")
    sql = "SELECT * FROM evidence_registry ev WHERE 1=1"
    params = []
    if criterion:
        sql += " AND ev.criterion = ?"
        params.append(criterion)
    if cycle:
        sql += " AND ev.cycle = ?"
        params.append(cycle)
    if user and user.get("role") == "department":
        department = user.get("department") or ""
        sql += """
            AND EXISTS (
                SELECT 1
                FROM change_atom ca_acl
                WHERE ca_acl.cycle4_criterion = ev.criterion
                  AND (
                    EXISTS (
                        SELECT 1
                        FROM department_action da_acl
                        WHERE da_acl.change_id = ca_acl.change_id
                          AND (
                            da_acl.primary_department = ?
                            OR (';' || COALESCE(da_acl.support_departments, '') || ';') LIKE ?
                          )
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM change_department cd_acl
                        JOIN departments d_acl ON d_acl.dept_id = cd_acl.dept_id
                        WHERE cd_acl.change_id = ca_acl.change_id
                          AND d_acl.dept_name = ?
                    )
                  )
            )
        """
        params.extend([department, f"%;{department};%", department])
    sql += " ORDER BY criterion, ev_id"
    return jsonify(query_all(sql, params))


@app.route("/api/evidence", methods=["POST"])
@admin_required
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
@admin_required
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
@admin_required
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
    user = current_user()
    sql = """
        SELECT ev.criterion, COUNT(*) as total,
               SUM(CASE WHEN cycle='3' THEN 1 ELSE 0 END) as cycle3,
               SUM(CASE WHEN cycle='4' THEN 1 ELSE 0 END) as cycle4,
               SUM(CASE WHEN is_reusable=1 THEN 1 ELSE 0 END) as reusable
        FROM evidence_registry ev
        WHERE 1=1
    """
    params = []
    if user and user.get("role") == "department":
        department = user.get("department") or ""
        sql += """
            AND EXISTS (
                SELECT 1
                FROM change_atom ca_acl
                WHERE ca_acl.cycle4_criterion = ev.criterion
                  AND (
                    EXISTS (
                        SELECT 1
                        FROM department_action da_acl
                        WHERE da_acl.change_id = ca_acl.change_id
                          AND (
                            da_acl.primary_department = ?
                            OR (';' || COALESCE(da_acl.support_departments, '') || ';') LIKE ?
                          )
                    )
                    OR EXISTS (
                        SELECT 1
                        FROM change_department cd_acl
                        JOIN departments d_acl ON d_acl.dept_id = cd_acl.dept_id
                        WHERE cd_acl.change_id = ca_acl.change_id
                          AND d_acl.dept_name = ?
                    )
                  )
            )
        """
        params.extend([department, f"%;{department};%", department])
    sql += " GROUP BY ev.criterion ORDER BY ev.criterion"
    rows = query_all(sql, params)
    return jsonify(rows)


# ─── 증빙자료 관리 페이지 ───────────────────────────────

@app.route("/evidence")
def evidence_page():
    return render_template("evidence.html")


# ─── AI 어시스턴트 API ─────────────────────────────────

@app.route("/api/ai/ask", methods=["POST"])
def api_ai_ask():
    """AI에게 질문 (RAG)"""
    user = current_user()
    data = request.get_json()
    query = data.get("query", "")
    criterion = data.get("criterion", "")
    context_type = data.get("context_type", "general")
    
    if not query and context_type == "general":
        return jsonify({"error": "질문 내용을 입력하세요"}), 400

    if user and user.get("role") == "department":
        if not criterion:
            return jsonify({"error": "부서 담당자는 접근 가능한 준거를 선택한 뒤 질문할 수 있습니다"}), 403
        department = user.get("department") or ""
        allowed = query_one(f"""
            SELECT 1 AS ok
            FROM change_atom ca
            WHERE ca.cycle4_criterion = ?
              AND {change_acl_sql("ca")}
            LIMIT 1
        """, (criterion, department, f"%;{department};%", department))
        if not allowed:
            return jsonify({"error": "접근 권한이 없는 준거입니다"}), 403
        
    result = ask_ai(DB_PATH, query, criterion, context_type)
    
    if "error" in result:
        return jsonify({"error": result["error"]}), result.get("status_code", 500)
        
    return jsonify(result)


# ─── 지식그래프 API ────────────────────────────────────

@app.route("/api/graph/data")
def api_graph_data():
    """지식그래프 시각화 데이터 (vis.js 호환)"""
    user = current_user()
    conn = get_db()
    
    # 노드 로드 (충분히 크게)
    if user and user.get("role") == "department":
        department = user.get("department") or ""
        node_rows = conn.execute(f"""
            WITH accessible_changes AS (
                SELECT ca.change_id, ca.cycle4_criterion
                FROM change_atom ca
                WHERE {change_acl_sql("ca")}
            )
            SELECT gn.node_id, gn.node_type, gn.title, gn.label
            FROM graph_nodes gn
            WHERE gn.change_id IN (SELECT change_id FROM accessible_changes)
               OR gn.criterion IN (SELECT cycle4_criterion FROM accessible_changes)
               OR gn.action_id IN (
                    SELECT da.action_id
                    FROM department_action da
                    JOIN accessible_changes ac ON ac.change_id = da.change_id
               )
               OR gn.department = ?
            LIMIT 1500
        """, (department, f"%;{department};%", department, department)).fetchall()
    else:
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
