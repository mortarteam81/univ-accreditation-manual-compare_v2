"""
Composite matching layer for 3rd/4th-cycle accreditation manual comparison.

This module keeps the existing one-to-one comparison tables intact and adds a
Phase 1.5 interpretation layer for many-to-one, one-to-many, and many-to-many
matching candidates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Iterable


STOPWORDS = {
    "대학",
    "있다",
    "하며",
    "하고",
    "한다",
    "또한",
    "관련",
    "자료",
    "최근",
    "기준",
    "대한",
    "통해",
    "위해",
    "위한",
    "결과",
    "운영",
    "반영",
    "구성원",
    "교육",
}

DEFAULT_MAX_PARTS = 3
DEFAULT_MIN_SCORE = 0.64
DEFAULT_MIN_COVERAGE = 0.62
DEFAULT_TOP_RANK = 5
DEFAULT_EDGE_SCORE = 0.18
DEFAULT_COMPONENT_EDGE_SCORE = 0.34
DEFAULT_CONCEPT_BRIDGE_MIN_SCORE = 0.50
REVIEW_STATE_COLUMNS = [
    "review_status",
    "decision_note",
    "reviewed_by_user_id",
    "reviewed_by_email",
    "reviewed_at",
    "applied_by_user_id",
    "applied_by_email",
    "applied_at",
]
CONCEPT_PATTERNS = {
    "development_plan": (
        "발전계획",
        "중장기 발전계획",
        "장단기 발전계획",
        "특성화계획",
    ),
    "plan_assessment": (
        "이행점검",
        "성과평가",
        "성과에 대한 평가",
        "평가 결과",
        "평가를 통해",
    ),
    "performance_management": (
        "성과관리",
        "성과관리체계",
        "자체평가",
        "질 관리",
        "교육만족도",
    ),
    "feedback": (
        "환류",
        "반영",
        "개선 실적",
        "개선실적",
    ),
}
CONCEPT_LABELS = {
    "development_plan": "발전계획",
    "plan_assessment": "성과평가/점검",
    "performance_management": "성과관리/질 관리",
    "feedback": "환류/반영",
}
SPLIT_TARGET_HINTS = {
    "1.2": "4주기 1.1 교육목표 및 발전계획",
    "5.1": "4주기 1.4 성과관리체계 구축 및 운영",
}


@dataclass(frozen=True)
class Source:
    source_id: str
    cycle: str
    criterion: str
    title: str
    section_type: str
    field_name: str
    content: str


def tokenize(value: str) -> set[str]:
    tokens = set()
    for raw in re.findall(r"[0-9A-Za-z가-힣]+", value or ""):
        token = raw.strip().lower()
        if len(token) <= 1 or token in STOPWORDS:
            continue
        tokens.add(token)
    return tokens


def concept_keys(value: str) -> set[str]:
    text = value or ""
    keys = set()
    for key, patterns in CONCEPT_PATTERNS.items():
        if any(pattern in text for pattern in patterns):
            keys.add(key)
    return keys


def source_concept_keys(source: Source) -> set[str]:
    return concept_keys(f"{source.title} {source.content}")


def concept_labels(keys: Iterable[str]) -> list[str]:
    return [CONCEPT_LABELS[key] for key in sorted(set(keys)) if key in CONCEPT_LABELS]


def json_dumps(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def json_loads(value, fallback=None):
    if not value:
        return [] if fallback is None else fallback
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return [] if fallback is None else fallback


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {
        row["name"]
        for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_composite_match_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS composite_match_candidate (
            composite_id TEXT PRIMARY KEY,
            direction TEXT NOT NULL,
            query_cycle TEXT NOT NULL,
            query_source_ids TEXT NOT NULL,
            candidate_source_ids TEXT NOT NULL,
            query_change_ids TEXT,
            candidate_change_ids TEXT,
            cycle4_criterion TEXT,
            cycle4_title TEXT,
            cycle3_criteria TEXT,
            cycle3_titles TEXT,
            section_type TEXT,
            field_name TEXT,
            score REAL,
            coverage_score REAL,
            precision_score REAL,
            title_score REAL,
            reciprocal_score REAL,
            single_best_score REAL,
            improvement_score REAL,
            evidence_reason TEXT,
            assignment_breakdown TEXT,
            review_status TEXT DEFAULT 'candidate',
            decision_note TEXT,
            reviewed_by_user_id INTEGER,
            reviewed_by_email TEXT,
            reviewed_at TEXT,
            applied_by_user_id INTEGER,
            applied_by_email TEXT,
            applied_at TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    ensure_column(conn, "composite_match_candidate", "decision_note", "TEXT")
    ensure_column(conn, "composite_match_candidate", "reviewed_by_user_id", "INTEGER")
    ensure_column(conn, "composite_match_candidate", "reviewed_by_email", "TEXT")
    ensure_column(conn, "composite_match_candidate", "reviewed_at", "TEXT")
    ensure_column(conn, "composite_match_candidate", "applied_by_user_id", "INTEGER")
    ensure_column(conn, "composite_match_candidate", "applied_by_email", "TEXT")
    ensure_column(conn, "composite_match_candidate", "applied_at", "TEXT")
    ensure_column(conn, "composite_match_candidate", "assignment_breakdown", "TEXT")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS composite_match_link (
            composite_id TEXT NOT NULL,
            change_id TEXT NOT NULL,
            source_id TEXT NOT NULL,
            role TEXT NOT NULL,
            PRIMARY KEY (composite_id, change_id, source_id, role)
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS composite_match_log (
            log_id INTEGER PRIMARY KEY AUTOINCREMENT,
            composite_id TEXT NOT NULL,
            action TEXT NOT NULL,
            old_status TEXT,
            new_status TEXT,
            note TEXT,
            related_change_ids TEXT,
            actor_user_id INTEGER,
            actor_email TEXT,
            actor_role TEXT,
            actor_department TEXT,
            ip_address TEXT,
            user_agent TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_composite_direction ON composite_match_candidate(direction)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_composite_cycle4 ON composite_match_candidate(cycle4_criterion)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_composite_score ON composite_match_candidate(score)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_composite_link_change ON composite_match_link(change_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_composite_log_composite ON composite_match_log(composite_id)"
    )
    conn.commit()


def reset_composite_matches(conn: sqlite3.Connection) -> None:
    ensure_composite_match_tables(conn)
    conn.execute("DELETE FROM composite_match_link")
    conn.execute("DELETE FROM composite_match_candidate")
    conn.commit()


def load_existing_review_state(conn: sqlite3.Connection) -> dict[str, dict]:
    ensure_composite_match_tables(conn)
    columns = ", ".join(["composite_id"] + REVIEW_STATE_COLUMNS)
    rows = conn.execute(f"SELECT {columns} FROM composite_match_candidate").fetchall()
    return {
        row["composite_id"]: {column: row[column] for column in REVIEW_STATE_COLUMNS}
        for row in rows
    }


def preserve_review_state(records: list[dict], existing_state: dict[str, dict]) -> None:
    for record in records:
        state = existing_state.get(record["composite_id"])
        if not state:
            continue
        record.update(state)


def load_sources(conn: sqlite3.Connection) -> dict[str, Source]:
    rows = conn.execute(
        """
        SELECT source_id, cycle, criterion, title, section_type, field_name, content
        FROM canonical_source
        WHERE TRIM(COALESCE(content, '')) <> ''
        """
    ).fetchall()
    return {
        row["source_id"]: Source(
            source_id=row["source_id"],
            cycle=str(row["cycle"] or ""),
            criterion=row["criterion"] or "",
            title=row["title"] or "",
            section_type=row["section_type"] or "",
            field_name=row["field_name"] or "",
            content=row["content"] or "",
        )
        for row in rows
    }


def load_change_links(conn: sqlite3.Connection) -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    source_to_changes: dict[str, set[str]] = defaultdict(set)
    change_to_sources: dict[str, set[str]] = defaultdict(set)
    rows = conn.execute(
        """
        SELECT change_id, source_id_3, source_id_4
        FROM change_atom
        """
    ).fetchall()
    for row in rows:
        change_id = row["change_id"]
        for source_id in (row["source_id_3"], row["source_id_4"]):
            if source_id:
                source_to_changes[source_id].add(change_id)
                change_to_sources[change_id].add(source_id)
    return source_to_changes, change_to_sources


def load_direct_cycle_pairs(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    rows = conn.execute(
        """
        SELECT source_id_3, source_id_4
        FROM change_atom
        WHERE source_id_3 IS NOT NULL
          AND source_id_4 IS NOT NULL
        """
    ).fetchall()
    return [(row["source_id_3"], row["source_id_4"]) for row in rows]


def load_edges(conn: sqlite3.Connection, top_rank: int, edge_score: float) -> list[dict]:
    rows = conn.execute(
        """
        SELECT *
        FROM global_match_candidate
        WHERE rank <= ?
          AND score >= ?
          AND query_source_id IS NOT NULL
          AND candidate_source_id IS NOT NULL
        ORDER BY query_source_id, rank, score DESC
        """,
        (top_rank, edge_score),
    ).fetchall()
    return [dict(row) for row in rows]


def text_metrics(query_text: str, candidate_texts: Iterable[str]) -> tuple[float, float, float]:
    query_tokens = tokenize(query_text)
    candidate_tokens: set[str] = set()
    for text in candidate_texts:
        candidate_tokens |= tokenize(text)
    if not query_tokens or not candidate_tokens:
        return 0.0, 0.0, 0.0
    overlap = query_tokens & candidate_tokens
    coverage = len(overlap) / len(query_tokens)
    precision = len(overlap) / len(candidate_tokens)
    harmonic = 2 * coverage * precision / (coverage + precision) if coverage + precision else 0.0
    return round(coverage, 4), round(precision, 4), round(harmonic, 4)


def title_score(query_sources: list[Source], candidate_sources: list[Source]) -> float:
    query_tokens: set[str] = set()
    candidate_tokens: set[str] = set()
    for source in query_sources:
        query_tokens |= tokenize(f"{source.criterion} {source.title}")
    for source in candidate_sources:
        candidate_tokens |= tokenize(f"{source.criterion} {source.title}")
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = query_tokens & candidate_tokens
    coverage = len(overlap) / len(query_tokens)
    precision = len(overlap) / len(candidate_tokens)
    return round((coverage + precision) / 2, 4)


def reciprocal_score(edge_lookup: dict[tuple[str, str], float], left_ids: list[str], right_ids: list[str]) -> float:
    checks = 0
    hits = 0
    for left in left_ids:
        for right in right_ids:
            checks += 1
            if (left, right) in edge_lookup or (right, left) in edge_lookup:
                hits += 1
    return round(hits / checks, 4) if checks else 0.0


def sources_compatible(left: Source | None, right: Source | None) -> bool:
    if not left or not right:
        return False
    if left.section_type != right.section_type:
        return False
    if left.field_name and right.field_name and left.field_name != right.field_name:
        return False
    return True


def single_best_coverage(query_sources: list[Source], candidate_sources: list[Source]) -> float:
    if not query_sources or not candidate_sources:
        return 0.0
    query_text = " ".join(source.content for source in query_sources)
    best = 0.0
    for candidate in candidate_sources:
        coverage, _precision, _harmonic = text_metrics(query_text, [candidate.content])
        best = max(best, coverage)
    return round(best, 4)


def all_parts_contribute(
    query_sources: list[Source],
    candidate_sources: list[Source],
    min_marginal: float = 0.06,
) -> bool:
    """Ensure every source in a composite candidate adds real explanatory coverage."""
    if len(candidate_sources) < 2:
        return False
    query_text = " ".join(source.content for source in query_sources)
    full_coverage, _precision, _harmonic = text_metrics(
        query_text,
        [source.content for source in candidate_sources],
    )
    for idx, _source in enumerate(candidate_sources):
        without = [source.content for pos, source in enumerate(candidate_sources) if pos != idx]
        coverage_without, _precision, _harmonic = text_metrics(query_text, without)
        if full_coverage - coverage_without < min_marginal:
            return False
    return True


def concept_bridge_contributes(
    direction: str,
    query_sources: list[Source],
    candidate_sources: list[Source],
    metrics: dict[str, float],
    min_coverage: float,
    min_score: float = DEFAULT_CONCEPT_BRIDGE_MIN_SCORE,
) -> bool:
    """Allow split/merge candidates where a source adds concept coverage, not token coverage."""
    if direction != "many_to_one" or len(query_sources) != 1 or len(candidate_sources) < 2:
        return False
    if query_sources[0].cycle != "4" or any(source.cycle != "3" for source in candidate_sources):
        return False
    if metrics["coverage_score"] < min_coverage or metrics["score"] < min_score:
        return False

    query_keys = source_concept_keys(query_sources[0])
    if not {"development_plan", "performance_management"}.issubset(query_keys):
        return False

    candidate_key_sets = [source_concept_keys(source) & query_keys for source in candidate_sources]
    if any(not keys for keys in candidate_key_sets):
        return False
    contributing_sets = [keys for keys in candidate_key_sets if keys]
    if len(contributing_sets) < 2:
        return False
    combined_keys = set().union(*contributing_sets)
    if not {"development_plan", "performance_management"}.issubset(combined_keys):
        return False

    best_single = max((len(keys) for keys in contributing_sets), default=0)
    if len(combined_keys) <= best_single:
        return False
    unique_contributors = 0
    for idx, keys in enumerate(candidate_key_sets):
        other_keys = set().union(
            *(other for pos, other in enumerate(candidate_key_sets) if pos != idx)
        )
        if keys - other_keys:
            unique_contributors += 1
    return unique_contributors >= 1


def composite_candidate_pass_kind(
    direction: str,
    query_sources: list[Source],
    candidate_sources: list[Source],
    metrics: dict[str, float],
    min_score: float,
    min_coverage: float,
) -> str | None:
    standard_pass = (
        metrics["coverage_score"] >= min_coverage
        and metrics["score"] >= min_score
        and all_parts_contribute(query_sources, candidate_sources)
        and (
            metrics["improvement_score"] >= 0.08
            or metrics["coverage_score"] >= 0.78
        )
    )
    if standard_pass:
        return "standard"
    if concept_bridge_contributes(direction, query_sources, candidate_sources, metrics, min_coverage):
        return "concept_bridge"
    return None


def adjacent_bonus(query_sources: list[Source], candidate_sources: list[Source]) -> float:
    def major_minor(criterion: str) -> tuple[int, int] | None:
        match = re.match(r"^(\d+)\.(\d+)", criterion or "")
        if not match:
            return None
        return int(match.group(1)), int(match.group(2))

    query_parts = [major_minor(source.criterion) for source in query_sources]
    candidate_parts = [major_minor(source.criterion) for source in candidate_sources]
    query_parts = [part for part in query_parts if part]
    candidate_parts = [part for part in candidate_parts if part]
    if not query_parts or not candidate_parts:
        return 0.0
    for q_major, q_minor in query_parts:
        for c_major, c_minor in candidate_parts:
            if q_major == c_major and abs(q_minor - c_minor) <= 1:
                return 0.05
    return 0.0


def composite_score(
    query_sources: list[Source],
    candidate_sources: list[Source],
    edge_lookup: dict[tuple[str, str], float],
) -> dict[str, float]:
    query_text = " ".join(source.content for source in query_sources)
    candidate_texts = [source.content for source in candidate_sources]
    coverage, precision, harmonic = text_metrics(query_text, candidate_texts)
    t_score = title_score(query_sources, candidate_sources)
    r_score = reciprocal_score(
        edge_lookup,
        [source.source_id for source in query_sources],
        [source.source_id for source in candidate_sources],
    )
    best_single = single_best_coverage(query_sources, candidate_sources)
    score = (
        coverage * 0.50
        + precision * 0.18
        + harmonic * 0.12
        + t_score * 0.12
        + r_score * 0.06
        + adjacent_bonus(query_sources, candidate_sources)
    )
    return {
        "score": round(min(score, 1.0), 4),
        "coverage_score": coverage,
        "precision_score": precision,
        "title_score": t_score,
        "reciprocal_score": r_score,
        "single_best_score": best_single,
        "improvement_score": round(max(0.0, coverage - best_single), 4),
    }


def group_change_ids(source_ids: Iterable[str], source_to_changes: dict[str, set[str]]) -> list[str]:
    change_ids: set[str] = set()
    for source_id in source_ids:
        change_ids |= source_to_changes.get(source_id, set())
    return sorted(change_ids)


def source_labels(sources: Iterable[Source]) -> str:
    labels = []
    for source in sources:
        label = f"{source.cycle}주기 {source.criterion} {source.title}".strip()
        labels.append(label)
    return " + ".join(labels)


def source_label(source: Source) -> str:
    return f"{source.cycle}주기 {source.criterion} {source.title}".strip()


def cycle4_target_label(source: Source | None) -> str:
    if not source:
        return ""
    return f"4주기 {source.criterion} {source.title}".strip()


def primary_target_hint(source: Source, fallback: str) -> str:
    if source.cycle == "3":
        for criterion_prefix, target in SPLIT_TARGET_HINTS.items():
            if source.criterion.startswith(criterion_prefix):
                target_prefix = " ".join(target.split()[:2])
                if fallback.startswith(target_prefix):
                    return fallback
                return target
    return fallback


def assignment_type_for_source(
    source: Source,
    query_target: str,
    hinted_target: str,
    query_keys: set[str],
    source_keys: set[str],
) -> tuple[str, str, str]:
    if hinted_target and hinted_target != query_target:
        if source.section_type in {"evidence", "checkpoints", "report", "notes"}:
            assignment_type = "shared_evidence"
            reason = (
                "이 항목은 원 준거의 주 맥락과 현재 4주기 준거의 검토 맥락을 함께 설명하므로 "
                "2차 검수에서 공통 근거 또는 분할 귀속 여부를 확인해야 합니다."
            )
        else:
            assignment_type = "moved_or_split_candidate"
            reason = (
                f"{hinted_target}에 주로 귀속되는 맥락이지만 "
                f"{query_target}의 성과평가·점검·환류 문맥과도 연결됩니다."
            )
        return assignment_type, hinted_target, reason

    if source_keys & {"development_plan"} and query_keys & {"performance_management"}:
        return (
            "shared_evidence",
            query_target,
            "발전계획 관련 표현이 현재 성과관리 문맥의 근거로 함께 쓰일 가능성이 있습니다.",
        )

    return (
        "primary",
        query_target,
        "현재 4주기 준거를 직접 설명하는 복합 대응 후보로 판단됩니다.",
    )


def build_assignment_breakdown(
    query_sources: list[Source],
    candidate_sources: list[Source],
) -> list[dict]:
    cycle4_sources = [source for source in query_sources + candidate_sources if source.cycle == "4"]
    primary_cycle4 = cycle4_sources[0] if cycle4_sources else None
    query_target = cycle4_target_label(primary_cycle4)
    query_keys = set().union(*(source_concept_keys(source) for source in query_sources))
    breakdown = []
    for source in candidate_sources:
        source_keys = source_concept_keys(source)
        if not source_keys:
            continue
        hinted_target = primary_target_hint(source, query_target)
        assignment_type, primary_target, reason = assignment_type_for_source(
            source,
            query_target,
            hinted_target,
            query_keys,
            source_keys,
        )
        secondary_target = query_target if primary_target != query_target else ""
        breakdown.append({
            "source_id": source.source_id,
            "source_label": source_label(source),
            "section_type": source.section_type,
            "field_name": source.field_name,
            "assignment_type": assignment_type,
            "primary_target": primary_target,
            "secondary_target": secondary_target,
            "concept_tags": concept_labels(source_keys),
            "assignment_reason": reason,
        })
    return breakdown


def make_composite_id(direction: str, query_ids: list[str], candidate_ids: list[str]) -> str:
    payload = json_dumps(
        {
            "direction": direction,
            "query_source_ids": query_ids,
            "candidate_source_ids": candidate_ids,
        }
    )
    digest = hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
    return f"cmp_{direction}_{digest}"


def build_record(
    direction: str,
    query_sources: list[Source],
    candidate_sources: list[Source],
    metrics: dict[str, float],
    source_to_changes: dict[str, set[str]],
    evidence_prefix: str,
    assignment_breakdown: list[dict] | None = None,
) -> dict:
    query_ids = sorted(source.source_id for source in query_sources)
    candidate_ids = sorted(source.source_id for source in candidate_sources)
    query_change_ids = group_change_ids(query_ids, source_to_changes)
    candidate_change_ids = group_change_ids(candidate_ids, source_to_changes)
    all_sources = query_sources + candidate_sources
    cycle4_sources = [source for source in all_sources if source.cycle == "4"]
    cycle3_sources = [source for source in all_sources if source.cycle == "3"]
    section = query_sources[0].section_type if query_sources else ""
    field = query_sources[0].field_name if query_sources else ""
    cycle4_criterion = ";".join(sorted({source.criterion for source in cycle4_sources}))
    cycle4_title = " + ".join(sorted({source.title for source in cycle4_sources if source.title}))
    cycle3_criteria = ";".join(sorted({source.criterion for source in cycle3_sources}))
    cycle3_titles = " + ".join(sorted({source.title for source in cycle3_sources if source.title}))
    evidence_reason = (
        f"{evidence_prefix}: {source_labels(candidate_sources)} ↔ {source_labels(query_sources)}. "
        f"coverage={metrics['coverage_score']:.2f}, title={metrics['title_score']:.2f}, "
        f"reciprocal={metrics['reciprocal_score']:.2f}, improvement={metrics['improvement_score']:.2f}"
    )
    return {
        "composite_id": make_composite_id(direction, query_ids, candidate_ids),
        "direction": direction,
        "query_cycle": query_sources[0].cycle if query_sources else "",
        "query_source_ids": json_dumps(query_ids),
        "candidate_source_ids": json_dumps(candidate_ids),
        "query_change_ids": json_dumps(query_change_ids),
        "candidate_change_ids": json_dumps(candidate_change_ids),
        "cycle4_criterion": cycle4_criterion,
        "cycle4_title": cycle4_title,
        "cycle3_criteria": cycle3_criteria,
        "cycle3_titles": cycle3_titles,
        "section_type": section,
        "field_name": field,
        "evidence_reason": evidence_reason,
        "assignment_breakdown": json_dumps(assignment_breakdown or build_assignment_breakdown(query_sources, candidate_sources)),
        "review_status": "candidate",
        "created_at": datetime.now().isoformat(timespec="seconds"),
        **metrics,
    }


def insert_records(conn: sqlite3.Connection, records: list[dict]) -> None:
    if not records:
        return
    columns = [
        "composite_id",
        "direction",
        "query_cycle",
        "query_source_ids",
        "candidate_source_ids",
        "query_change_ids",
        "candidate_change_ids",
        "cycle4_criterion",
        "cycle4_title",
        "cycle3_criteria",
        "cycle3_titles",
        "section_type",
        "field_name",
        "score",
        "coverage_score",
        "precision_score",
        "title_score",
        "reciprocal_score",
        "single_best_score",
        "improvement_score",
        "evidence_reason",
        "assignment_breakdown",
        "review_status",
        "decision_note",
        "reviewed_by_user_id",
        "reviewed_by_email",
        "reviewed_at",
        "applied_by_user_id",
        "applied_by_email",
        "applied_at",
        "created_at",
    ]
    placeholders = ", ".join(["?"] * len(columns))
    conn.executemany(
        f"""
        INSERT OR REPLACE INTO composite_match_candidate ({", ".join(columns)})
        VALUES ({placeholders})
        """,
        [tuple(record.get(col) for col in columns) for record in records],
    )


def insert_links(
    conn: sqlite3.Connection,
    records: list[dict],
    source_to_changes: dict[str, set[str]],
) -> None:
    rows = []
    for record in records:
        for role, key in (("query", "query_source_ids"), ("candidate", "candidate_source_ids")):
            for source_id in json_loads(record[key]):
                for change_id in source_to_changes.get(source_id, set()):
                    rows.append((record["composite_id"], change_id, source_id, role))
    conn.executemany(
        """
        INSERT OR IGNORE INTO composite_match_link (composite_id, change_id, source_id, role)
        VALUES (?, ?, ?, ?)
        """,
        rows,
    )


def candidate_groups(
    edges: list[dict],
    sources: dict[str, Source],
    query_cycle: str,
    candidate_cycle: str,
) -> dict[str, list[str]]:
    grouped: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for edge in edges:
        if str(edge.get("query_cycle")) != query_cycle or str(edge.get("candidate_cycle")) != candidate_cycle:
            continue
        query_id = edge["query_source_id"]
        candidate_id = edge["candidate_source_id"]
        query = sources.get(query_id)
        candidate = sources.get(candidate_id)
        if not sources_compatible(query, candidate):
            continue
        grouped[query_id].append((candidate_id, float(edge.get("score") or 0.0)))
    result: dict[str, list[str]] = {}
    for query_id, values in grouped.items():
        ordered = []
        seen = set()
        for candidate_id, _score in sorted(values, key=lambda item: item[1], reverse=True):
            if candidate_id in seen:
                continue
            seen.add(candidate_id)
            ordered.append(candidate_id)
        result[query_id] = ordered
    return result


def direct_candidates_by_cycle4(
    direct_pairs: list[tuple[str, str]],
    sources: dict[str, Source],
) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for source_id_3, source_id_4 in direct_pairs:
        source3 = sources.get(source_id_3)
        source4 = sources.get(source_id_4)
        if not source3 or not source4:
            continue
        if source3.cycle != "3" or source4.cycle != "4":
            continue
        if not sources_compatible(source4, source3):
            continue
        grouped[source4.source_id].add(source3.source_id)
    return grouped


def edge_candidates_by_cycle4(
    edges: list[dict],
    sources: dict[str, Source],
) -> dict[str, set[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        query = sources.get(edge["query_source_id"])
        candidate = sources.get(edge["candidate_source_id"])
        if not sources_compatible(query, candidate):
            continue
        if query.cycle == "4" and candidate.cycle == "3":
            grouped[query.source_id].add(candidate.source_id)
        elif query.cycle == "3" and candidate.cycle == "4":
            grouped[candidate.source_id].add(query.source_id)
    return grouped


def generate_directional_records(
    direction: str,
    grouped: dict[str, list[str]],
    sources: dict[str, Source],
    source_to_changes: dict[str, set[str]],
    edge_lookup: dict[tuple[str, str], float],
    max_parts: int,
    min_score: float,
    min_coverage: float,
) -> list[dict]:
    records: list[dict] = []
    seen_ids = set()
    for query_id, candidates in grouped.items():
        query = sources.get(query_id)
        if not query:
            continue
        max_size = min(max_parts, len(candidates))
        for size in range(2, max_size + 1):
            for combo_ids in combinations(candidates, size):
                combo_sources = [sources[candidate_id] for candidate_id in combo_ids if candidate_id in sources]
                if len(combo_sources) != size:
                    continue
                query_sources = [query]
                candidate_sources = combo_sources
                metrics = composite_score(query_sources, candidate_sources, edge_lookup)
                pass_kind = composite_candidate_pass_kind(
                    direction,
                    query_sources,
                    candidate_sources,
                    metrics,
                    min_score,
                    min_coverage,
                )
                if not pass_kind:
                    continue
                evidence_prefix = (
                    "통합/재구성 후보"
                    if direction == "many_to_one"
                    else "분리/재배치 후보"
                )
                if pass_kind == "concept_bridge":
                    evidence_prefix = "개념 브릿지 통합 후보"
                record = build_record(
                    direction,
                    query_sources,
                    candidate_sources,
                    metrics,
                    source_to_changes,
                    evidence_prefix,
                )
                if record["composite_id"] in seen_ids:
                    continue
                seen_ids.add(record["composite_id"])
                records.append(record)
    return records


def generate_anchor_records(
    direct_pairs: list[tuple[str, str]],
    edges: list[dict],
    sources: dict[str, Source],
    source_to_changes: dict[str, set[str]],
    edge_lookup: dict[tuple[str, str], float],
    max_parts: int,
    min_score: float,
    min_coverage: float,
) -> list[dict]:
    direct_by_anchor = direct_candidates_by_cycle4(direct_pairs, sources)
    edge_by_anchor = edge_candidates_by_cycle4(edges, sources)
    records: list[dict] = []
    seen_ids = set()
    for anchor_id, direct_ids in direct_by_anchor.items():
        anchor = sources.get(anchor_id)
        if not anchor:
            continue
        edge_ids = sorted(edge_by_anchor.get(anchor_id, set()) - direct_ids)
        if not edge_ids:
            continue
        for direct_id in sorted(direct_ids):
            max_edge_size = min(max_parts - 1, len(edge_ids))
            for size in range(1, max_edge_size + 1):
                for combo_ids in combinations(edge_ids, size):
                    candidate_ids = sorted({direct_id, *combo_ids})
                    if len(candidate_ids) < 2 or len(candidate_ids) > max_parts:
                        continue
                    candidate_sources = [sources[candidate_id] for candidate_id in candidate_ids if candidate_id in sources]
                    if len(candidate_sources) != len(candidate_ids):
                        continue
                    query_sources = [anchor]
                    metrics = composite_score(query_sources, candidate_sources, edge_lookup)
                    pass_kind = composite_candidate_pass_kind(
                        "many_to_one",
                        query_sources,
                        candidate_sources,
                        metrics,
                        min_score,
                        min_coverage,
                    )
                    if not pass_kind:
                        continue
                    evidence_prefix = "직접매핑+후보 통합 후보"
                    if pass_kind == "concept_bridge":
                        evidence_prefix = "직접매핑+후보 개념 브릿지 후보"
                    record = build_record(
                        "many_to_one",
                        query_sources,
                        candidate_sources,
                        metrics,
                        source_to_changes,
                        evidence_prefix,
                    )
                    if record["composite_id"] in seen_ids:
                        continue
                    seen_ids.add(record["composite_id"])
                    records.append(record)
    return records


def generate_many_to_many_records(
    edges: list[dict],
    sources: dict[str, Source],
    source_to_changes: dict[str, set[str]],
    edge_lookup: dict[tuple[str, str], float],
    min_score: float,
    min_coverage: float,
    component_edge_score: float,
) -> list[dict]:
    adjacency: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        if float(edge.get("score") or 0.0) < component_edge_score:
            continue
        query = sources.get(edge["query_source_id"])
        candidate = sources.get(edge["candidate_source_id"])
        if not sources_compatible(query, candidate):
            continue
        adjacency[query.source_id].add(candidate.source_id)
        adjacency[candidate.source_id].add(query.source_id)

    records: list[dict] = []
    visited: set[str] = set()
    for source_id in list(adjacency):
        if source_id in visited:
            continue
        stack = [source_id]
        component: set[str] = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency.get(current, set()) - component)
        visited |= component
        cycle3 = sorted([sources[sid] for sid in component if sources.get(sid) and sources[sid].cycle == "3"], key=lambda s: s.source_id)
        cycle4 = sorted([sources[sid] for sid in component if sources.get(sid) and sources[sid].cycle == "4"], key=lambda s: s.source_id)
        if len(cycle3) < 2 or len(cycle4) < 2:
            continue
        if len(cycle3) > 4 or len(cycle4) > 4:
            continue
        metrics_forward = composite_score(cycle4, cycle3, edge_lookup)
        metrics_reverse = composite_score(cycle3, cycle4, edge_lookup)
        if not all_parts_contribute(cycle4, cycle3) or not all_parts_contribute(cycle3, cycle4):
            continue
        coverage = round((metrics_forward["coverage_score"] + metrics_reverse["coverage_score"]) / 2, 4)
        score = round((metrics_forward["score"] + metrics_reverse["score"]) / 2, 4)
        if coverage < min_coverage or score < min_score:
            continue
        metrics = dict(metrics_forward)
        metrics["score"] = score
        metrics["coverage_score"] = coverage
        metrics["precision_score"] = round((metrics_forward["precision_score"] + metrics_reverse["precision_score"]) / 2, 4)
        metrics["title_score"] = round((metrics_forward["title_score"] + metrics_reverse["title_score"]) / 2, 4)
        metrics["reciprocal_score"] = round((metrics_forward["reciprocal_score"] + metrics_reverse["reciprocal_score"]) / 2, 4)
        metrics["single_best_score"] = round((metrics_forward["single_best_score"] + metrics_reverse["single_best_score"]) / 2, 4)
        metrics["improvement_score"] = round((metrics_forward["improvement_score"] + metrics_reverse["improvement_score"]) / 2, 4)
        records.append(
            build_record(
                "many_to_many",
                cycle4,
                cycle3,
                metrics,
                source_to_changes,
                "복수 준거 재구성 후보",
            )
        )
    return records


def summarize(conn: sqlite3.Connection) -> dict:
    direction_rows = conn.execute(
        """
        SELECT direction, COUNT(*) AS count
        FROM composite_match_candidate
        GROUP BY direction
        ORDER BY direction
        """
    ).fetchall()
    criterion_rows = conn.execute(
        """
        SELECT cycle4_criterion, COUNT(*) AS count
        FROM composite_match_candidate
        GROUP BY cycle4_criterion
        ORDER BY count DESC, cycle4_criterion
        LIMIT 12
        """
    ).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM composite_match_candidate").fetchone()[0]
    return {
        "total": total,
        "by_direction": {row["direction"]: row["count"] for row in direction_rows},
        "top_criteria": [dict(row) for row in criterion_rows],
    }


def rebuild_composite_matches(
    conn: sqlite3.Connection,
    *,
    max_parts: int = DEFAULT_MAX_PARTS,
    min_score: float = DEFAULT_MIN_SCORE,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    top_rank: int = DEFAULT_TOP_RANK,
    edge_score: float = DEFAULT_EDGE_SCORE,
    component_edge_score: float = DEFAULT_COMPONENT_EDGE_SCORE,
) -> dict:
    conn.row_factory = sqlite3.Row
    existing_review_state = load_existing_review_state(conn)
    reset_composite_matches(conn)
    sources = load_sources(conn)
    source_to_changes, _change_to_sources = load_change_links(conn)
    direct_pairs = load_direct_cycle_pairs(conn)
    edges = load_edges(conn, top_rank, edge_score)
    edge_lookup = {
        (edge["query_source_id"], edge["candidate_source_id"]): float(edge.get("score") or 0.0)
        for edge in edges
    }

    many_to_one = generate_directional_records(
        "many_to_one",
        candidate_groups(edges, sources, "4", "3"),
        sources,
        source_to_changes,
        edge_lookup,
        max_parts,
        min_score,
        min_coverage,
    )
    anchor_many_to_one = generate_anchor_records(
        direct_pairs,
        edges,
        sources,
        source_to_changes,
        edge_lookup,
        max_parts,
        min_score,
        min_coverage,
    )
    one_to_many = generate_directional_records(
        "one_to_many",
        candidate_groups(edges, sources, "3", "4"),
        sources,
        source_to_changes,
        edge_lookup,
        max_parts,
        min_score,
        min_coverage,
    )
    many_to_many = generate_many_to_many_records(
        edges,
        sources,
        source_to_changes,
        edge_lookup,
        min_score,
        min_coverage,
        component_edge_score,
    )
    records_by_id = {}
    for record in many_to_one + anchor_many_to_one + one_to_many + many_to_many:
        existing = records_by_id.get(record["composite_id"])
        if not existing or record["score"] > existing["score"]:
            records_by_id[record["composite_id"]] = record
    records = sorted(records_by_id.values(), key=lambda item: item["score"], reverse=True)
    preserve_review_state(records, existing_review_state)
    insert_records(conn, records)
    insert_links(conn, records, source_to_changes)
    conn.commit()
    summary = summarize(conn)
    summary["inserted"] = len(records)
    return summary


def load_composite_candidates_for_change(conn: sqlite3.Connection, change_id: str, limit: int = 8) -> list[dict]:
    conn.row_factory = sqlite3.Row
    change_sources = {
        row["source_id"]
        for row in conn.execute(
            """
            SELECT source_id_3 AS source_id FROM change_atom WHERE change_id = ?
            UNION
            SELECT source_id_4 AS source_id FROM change_atom WHERE change_id = ?
            """,
            (change_id, change_id),
        ).fetchall()
        if row["source_id"]
    }
    rows = conn.execute(
        """
        SELECT DISTINCT c.*
        FROM composite_match_candidate c
        JOIN composite_match_link l ON l.composite_id = c.composite_id
        WHERE l.change_id = ?
        ORDER BY c.score DESC, c.coverage_score DESC, c.composite_id
        LIMIT 40
        """,
        (change_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        query_ids = json_loads(item.get("query_source_ids"))
        candidate_ids = json_loads(item.get("candidate_source_ids"))
        item["change_source_match_count"] = len((set(query_ids) | set(candidate_ids)) & change_sources)
        source_ids = query_ids + candidate_ids
        source_rows = conn.execute(
            f"""
            SELECT source_id, cycle, criterion, title, section_type, field_name, content
            FROM canonical_source
            WHERE source_id IN ({",".join(["?"] * len(source_ids))})
            """,
            source_ids,
        ).fetchall() if source_ids else []
        source_map = {source["source_id"]: dict(source) for source in source_rows}
        for source in source_map.values():
            content = source.get("content") or ""
            source["content_preview"] = content[:180] + ("..." if len(content) > 180 else "")
            source.pop("content", None)
        item["query_source_ids"] = query_ids
        item["candidate_source_ids"] = candidate_ids
        item["query_change_ids"] = json_loads(item.get("query_change_ids"))
        item["candidate_change_ids"] = json_loads(item.get("candidate_change_ids"))
        item["assignment_breakdown"] = json_loads(item.get("assignment_breakdown"))
        item["query_sources"] = [source_map[source_id] for source_id in query_ids if source_id in source_map]
        item["candidate_sources"] = [source_map[source_id] for source_id in candidate_ids if source_id in source_map]
        result.append(item)
    result.sort(
        key=lambda item: (
            item["change_source_match_count"],
            item.get("score") or 0,
            item.get("coverage_score") or 0,
        ),
        reverse=True,
    )
    return result[:limit]


def main() -> int:
    parser = argparse.ArgumentParser(description="Build composite match candidates.")
    parser.add_argument("--db", default=str(Path(__file__).parent / "accreditation_review.db"))
    parser.add_argument("--rebuild", action="store_true", help="Rebuild composite candidate tables.")
    parser.add_argument("--json-summary", action="store_true", help="Print summary as JSON.")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE)
    parser.add_argument("--min-coverage", type=float, default=DEFAULT_MIN_COVERAGE)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    if args.rebuild:
        summary = rebuild_composite_matches(
            conn,
            min_score=args.min_score,
            min_coverage=args.min_coverage,
        )
    else:
        ensure_composite_match_tables(conn)
        summary = summarize(conn)
    conn.close()
    if args.json_summary:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Composite candidates: {summary['total']}")
        for direction, count in summary.get("by_direction", {}).items():
            print(f"  {direction}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
