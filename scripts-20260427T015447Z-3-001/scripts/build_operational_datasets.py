#!/usr/bin/env python3
"""Build operational accreditation-prep datasets from canonical outputs.

This script is intentionally a second-stage pipeline. It reads the verified
source/candidate outputs produced by ``build_canonical_datasets.py`` and adds
review-oriented global matching, department action fields, Graph RAG exports,
manual review packets, and dashboard-ready summary tables.

No external LLM or network service is used here. All matching is heuristic and
must remain review-oriented unless explicitly confirmed by a human.
"""

from __future__ import annotations

import csv
import datetime as dt
import difflib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "outputs" / "canonical_datasets"
REVIEW_PACKET_DIR = ROOT / "outputs" / "review_packets"
DASHBOARD_DIR = ROOT / "outputs" / "dashboard_mvp"

MANUAL_REVIEW_CRITERIA = {"1.5", "3.4", "4.2", "4.3"}
REPORT_MATCH_THRESHOLD = 0.35

HIGH_IMPACT_CATEGORIES = {
    "기준값/정량",
    "산식/기준산정",
    "실적기간",
    "증빙",
    "면담",
    "시설방문",
}

CHANGE_REVIEW_TYPES = {"신설후보", "삭제후보", "이동후보", "삭제/이동후보"}


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def compare_key(value: str) -> str:
    value = normalize_text(value).lower()
    return re.sub(r"[^\w가-힣]", "", value)


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"[^0-9A-Za-z가-힣_.:-]+", "_", value.strip())
    return value.strip("_") or "unknown"


def read_jsonl(name: str) -> list[dict[str, Any]]:
    path = DATA_DIR / f"{name}.jsonl"
    if not path.exists():
        raise SystemExit(f"Missing input dataset: {path}")
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_dataset(directory: Path, name: str, rows: list[dict[str, Any]]) -> None:
    write_jsonl(directory / f"{name}.jsonl", rows)
    write_csv(directory / f"{name}.csv", rows)


def text_tokens(value: str) -> set[str]:
    return set(re.findall(r"[0-9A-Za-z가-힣]+", normalize_text(value).lower()))


def ngrams(value: str, n: int = 3) -> set[str]:
    key = compare_key(value)
    if not key:
        return set()
    if len(key) <= n:
        return {key}
    return {key[idx : idx + n] for idx in range(len(key) - n + 1)}


def jaccard(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def similarity(left: str, right: str) -> float:
    return difflib.SequenceMatcher(None, compare_key(left), compare_key(right)).ratio()


def criterion_pair_key(cycle4: str, cycle3: str) -> tuple[str, str]:
    return (cycle4 or "", cycle3 or "")


def mapping_pairs(mapping_rows: list[dict[str, Any]]) -> set[tuple[str, str]]:
    pairs: set[tuple[str, str]] = set()
    for row in mapping_rows:
        pairs.add(criterion_pair_key(row.get("cycle4_criterion", ""), row.get("cycle3_criterion", "")))
    return pairs


def is_manual_review_atom(row: dict[str, Any]) -> bool:
    return row.get("cycle4_criterion") in MANUAL_REVIEW_CRITERIA or row.get("cycle3_criterion") in MANUAL_REVIEW_CRITERIA


def parse_similarity(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def atom_needs_global_search(row: dict[str, Any]) -> bool:
    if row.get("change_type") == "유지" and row.get("verification_status") == "confirmed":
        return False
    sim = parse_similarity(row.get("similarity", ""))
    return (
        not row.get("source_id_4")
        or not row.get("source_id_3")
        or row.get("change_type") in CHANGE_REVIEW_TYPES
        or (sim is not None and sim < 0.72)
    )


def candidate_direction(row: dict[str, Any]) -> tuple[str, str]:
    if row.get("source_id_4"):
        return row["source_id_4"], "c4_to_c3"
    return row.get("source_id_3", ""), "c3_to_c4"


def target_cycle_for_direction(direction: str) -> str:
    return "3" if direction == "c4_to_c3" else "4"


def criterion_mapping_match(
    query: dict[str, Any],
    candidate: dict[str, Any],
    pairs: set[tuple[str, str]],
) -> bool:
    if query.get("cycle") == "4":
        return criterion_pair_key(query.get("criterion", ""), candidate.get("criterion", "")) in pairs
    return criterion_pair_key(candidate.get("criterion", ""), query.get("criterion", "")) in pairs


def score_candidate(
    query: dict[str, Any],
    candidate: dict[str, Any],
    pairs: set[tuple[str, str]],
) -> dict[str, Any]:
    diff = similarity(query.get("content", ""), candidate.get("content", ""))
    gram = jaccard(ngrams(query.get("content", "")), ngrams(candidate.get("content", "")))
    token = jaccard(text_tokens(query.get("content", "")), text_tokens(candidate.get("content", "")))
    same_section = query.get("section_type") == candidate.get("section_type")
    same_field = bool(query.get("field_name")) and query.get("field_name") == candidate.get("field_name")
    same_criterion = query.get("criterion") == candidate.get("criterion")
    mapped_criterion = criterion_mapping_match(query, candidate, pairs)

    score = (diff * 0.45) + (gram * 0.30) + (token * 0.15)
    if same_section:
        score += 0.06
    if same_field:
        score += 0.04
    if mapped_criterion:
        score += 0.08
    elif same_criterion:
        score += 0.03
    score = min(score, 1.0)

    reasons = [
        f"difflib={diff:.3f}",
        f"ngram={gram:.3f}",
        f"token={token:.3f}",
    ]
    if same_section:
        reasons.append("same_section")
    if same_field:
        reasons.append("same_field")
    if mapped_criterion:
        reasons.append("criterion_mapping_candidate")
    elif same_criterion:
        reasons.append("same_criterion_number")

    return {
        "score": score,
        "difflib_similarity": diff,
        "ngram_jaccard": gram,
        "token_overlap": token,
        "section_match": same_section,
        "field_match": same_field,
        "criterion_mapping_match": mapped_criterion,
        "match_reason": ";".join(reasons),
    }


def global_status(top_score: float | None) -> str:
    if top_score is None:
        return "not_applicable"
    if top_score >= 0.82:
        return "strong_candidate"
    if top_score >= 0.65:
        return "possible_candidate"
    if top_score >= REPORT_MATCH_THRESHOLD:
        return "weak_candidate"
    return "no_candidate"


def build_global_matches(
    change_rows: list[dict[str, Any]],
    sources_by_id: dict[str, dict[str, Any]],
    sources_by_cycle: dict[str, list[dict[str, Any]]],
    pairs: set[tuple[str, str]],
) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    all_matches: list[dict[str, Any]] = []
    matches_by_change: dict[str, list[dict[str, Any]]] = {}

    for atom in change_rows:
        if not atom_needs_global_search(atom):
            matches_by_change[atom["change_id"]] = []
            continue
        query_source_id, direction = candidate_direction(atom)
        if not query_source_id or query_source_id not in sources_by_id:
            matches_by_change[atom["change_id"]] = []
            continue

        query = sources_by_id[query_source_id]
        target_cycle = target_cycle_for_direction(direction)
        scored: list[dict[str, Any]] = []
        for candidate in sources_by_cycle[target_cycle]:
            metrics = score_candidate(query, candidate, pairs)
            scored.append((metrics["score"], candidate, metrics))
        scored.sort(key=lambda item: item[0], reverse=True)

        rows_for_change: list[dict[str, Any]] = []
        for rank, (score, candidate, metrics) in enumerate(scored[:5], start=1):
            row = {
                "match_id": f"gmatch_{len(all_matches) + 1:06d}",
                "change_id": atom["change_id"],
                "rank": str(rank),
                "candidate_direction": direction,
                "query_source_id": query["source_id"],
                "query_cycle": query["cycle"],
                "query_criterion": query["criterion"],
                "query_title": query["title"],
                "query_section_type": query["section_type"],
                "query_field_name": query.get("field_name", ""),
                "query_text": query["content"],
                "candidate_source_id": candidate["source_id"],
                "candidate_cycle": candidate["cycle"],
                "candidate_criterion": candidate["criterion"],
                "candidate_title": candidate["title"],
                "candidate_section_type": candidate["section_type"],
                "candidate_field_name": candidate.get("field_name", ""),
                "candidate_text": candidate["content"],
                "score": f"{score:.3f}",
                "difflib_similarity": f"{metrics['difflib_similarity']:.3f}",
                "ngram_jaccard": f"{metrics['ngram_jaccard']:.3f}",
                "token_overlap": f"{metrics['token_overlap']:.3f}",
                "section_match": str(metrics["section_match"]).lower(),
                "field_match": str(metrics["field_match"]).lower(),
                "criterion_mapping_match": str(metrics["criterion_mapping_match"]).lower(),
                "match_reason": metrics["match_reason"],
                "candidate_only_warning": "Global matching is heuristic and must be reviewed before accreditation judgment.",
            }
            all_matches.append(row)
            rows_for_change.append(row)
        matches_by_change[atom["change_id"]] = rows_for_change

    return all_matches, matches_by_change


def review_reasons(atom: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if is_manual_review_atom(atom):
        reasons.append("manual_complex_nm_criterion")
    if not atom.get("source_id_4"):
        reasons.append("source_only_delete_or_move_review")
    if not atom.get("source_id_3"):
        reasons.append("target_only_new_or_move_review")
    sim = parse_similarity(atom.get("similarity", ""))
    if sim is not None and sim < 0.72:
        reasons.append("low_similarity_match")
    if atom.get("verification_status") in {"candidate", "needs_review"}:
        reasons.append(f"{atom.get('verification_status')}_status")
    categories = set(filter(None, atom.get("change_categories", "").split(";")))
    if categories & HIGH_IMPACT_CATEGORIES:
        reasons.append("evidence_or_metric_impact")
    return reasons or ["no_manual_review_trigger"]


def enrich_change_atoms(
    change_rows: list[dict[str, Any]],
    matches_by_change: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    for atom in change_rows:
        if is_manual_review_atom(atom):
            atom["verification_status"] = "needs_review"
            atom["manual_review_required"] = "true"

        matches = matches_by_change.get(atom["change_id"], [])
        reportable_count = sum(1 for row in matches if float(row["score"]) >= REPORT_MATCH_THRESHOLD)
        top_score = float(matches[0]["score"]) if matches else None
        if not atom_needs_global_search(atom):
            status = "not_applicable"
        else:
            status = global_status(top_score)
        reasons = review_reasons(atom)

        official_needed = (
            atom.get("verification_status") != "confirmed"
            or is_manual_review_atom(atom)
            or status in {"strong_candidate", "possible_candidate", "weak_candidate", "no_candidate"}
        )
        atom["global_match_status"] = status
        atom["global_candidate_count"] = str(reportable_count)
        atom["review_reason"] = ";".join(reasons)
        atom["human_review_status"] = "pending" if official_needed else "not_required"
        atom["official_confirmation_needed"] = str(official_needed).lower()
    return change_rows


def split_departments(value: str) -> tuple[str, str]:
    departments = [normalize_text(part) for part in re.split(r"[,;/]", value or "") if normalize_text(part)]
    if not departments:
        return "", ""
    return departments[0], ";".join(departments[1:])


def infer_action_type(atom: dict[str, Any]) -> str:
    categories = set(filter(None, atom.get("change_categories", "").split(";")))
    change_type = atom.get("change_type", "")
    if change_type == "신설후보":
        return "new_requirement_review"
    if change_type in {"삭제후보", "삭제/이동후보"}:
        return "deletion_or_move_review"
    if change_type == "이동후보":
        return "move_review"
    if categories & {"기준값/정량", "산식/기준산정", "실적기간"}:
        return "metric_or_standard_update"
    if categories & {"증빙", "면담", "시설방문"}:
        return "evidence_preparation_update"
    if change_type == "변경":
        return "content_change_review"
    return "monitoring_review"


def extract_data_period(text: str) -> str:
    patterns = [
        r"최근\s*[0-9]+년",
        r"[0-9]+년\s*자료",
        r"[0-9]{4}\s*학년도",
        r"[0-9]{4}\s*년",
        r"기준연도",
        r"평가\s*시점",
        r"회계연도",
    ]
    found: list[str] = []
    for pattern in patterns:
        found.extend(normalize_text(match) for match in re.findall(pattern, text))
    return ";".join(dict.fromkeys(found))


def extract_metric_or_threshold(text: str) -> str:
    found = re.findall(r"[0-9]+(?:\.[0-9]+)?\s*(?:%|원|명|건|천원|시간|학점|회|년)", text)
    keyword_hits = [kw for kw in ["기준값", "산출", "비율", "평균", "충원율", "확보율", "환원율", "수용률"] if kw in text]
    values = list(dict.fromkeys([normalize_text(item) for item in found] + keyword_hits))
    return ";".join(values[:12])


def refined_risk(atom: dict[str, Any]) -> str:
    categories = set(filter(None, atom.get("change_categories", "").split(";")))
    change_type = atom.get("change_type", "")
    global_status_value = atom.get("global_match_status", "")
    if is_manual_review_atom(atom):
        return "high"
    if categories & {"기준값/정량", "산식/기준산정", "면담", "시설방문"} and change_type != "유지":
        return "high"
    if change_type in CHANGE_REVIEW_TYPES and categories & HIGH_IMPACT_CATEGORIES:
        return "high"
    if change_type in CHANGE_REVIEW_TYPES and global_status_value in {"no_candidate", "weak_candidate"}:
        return "high"
    if atom.get("verification_status") == "needs_review" and categories & {"증빙", "실적기간"}:
        return "medium"
    if change_type == "변경" or atom.get("verification_status") in {"candidate", "needs_review"}:
        return "medium"
    return "low"


def source_support_level(atom: dict[str, Any]) -> str:
    if atom.get("source_id_4") and atom.get("source_id_3"):
        if atom.get("verification_status") == "confirmed":
            return "source_json_supported"
        return "source_json_comparative_candidate"
    return "source_json_single_side_review"


def enrich_department_actions(
    action_rows: list[dict[str, Any]],
    atoms_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    for action in action_rows:
        atom = atoms_by_id[action["change_id"]]
        primary, support = split_departments(action.get("department_candidate", ""))
        source_text = atom.get("source_text_4") or atom.get("source_text_3") or action.get("preparation_task", "")
        risk = refined_risk(atom)
        action["verification_status"] = atom.get("verification_status", action.get("verification_status", ""))
        action["risk_level"] = risk
        action["priority"] = {"high": "1", "medium": "2", "low": "3"}[risk]
        action["notice_required"] = str(risk in {"high", "medium"}).lower()
        action["action_type"] = infer_action_type(atom)
        action["primary_department"] = primary
        action["support_departments"] = support
        action["data_period"] = extract_data_period(source_text)
        action["metric_or_threshold"] = extract_metric_or_threshold(source_text)
        action["evidence_link"] = atom.get("source_id_4") or atom.get("source_id_3")
        action["confirmed_by"] = ""
        action["confirmed_at"] = ""
        action["source_support_level"] = source_support_level(atom)
        action["official_confirmation_needed"] = atom.get("official_confirmation_needed", "true")
    return action_rows


def build_review_queue(
    atoms: list[dict[str, Any]],
    actions_by_change: dict[str, dict[str, Any]],
    matches_by_change: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for atom in atoms:
        action = actions_by_change.get(atom["change_id"], {})
        risk = action.get("risk_level", refined_risk(atom))
        include = (
            atom.get("human_review_status") == "pending"
            or risk in {"high", "medium"}
            or atom.get("official_confirmation_needed") == "true"
        )
        if not include:
            continue
        top = (matches_by_change.get(atom["change_id"]) or [{}])[0]
        categories = set(filter(None, atom.get("change_categories", "").split(";")))
        rows.append(
            {
                "review_id": f"review_{len(rows) + 1:05d}",
                "priority": {"high": "1", "medium": "2", "low": "3"}[risk],
                "risk_level": risk,
                "review_topic": f"{atom.get('cycle4_criterion') or atom.get('cycle3_criterion')} {atom.get('cycle4_title') or atom.get('cycle3_title')}",
                "review_reason": atom.get("review_reason", ""),
                "human_review_status": atom.get("human_review_status", "pending"),
                "official_confirmation_needed": atom.get("official_confirmation_needed", "true"),
                "global_match_status": atom.get("global_match_status", ""),
                "global_candidate_count": atom.get("global_candidate_count", "0"),
                "change_id": atom["change_id"],
                "change_type": atom.get("change_type", ""),
                "section_type": atom.get("section_type", ""),
                "cycle4_criterion": atom.get("cycle4_criterion", ""),
                "cycle4_title": atom.get("cycle4_title", ""),
                "cycle3_criterion": atom.get("cycle3_criterion", ""),
                "cycle3_title": atom.get("cycle3_title", ""),
                "evidence_impact": str(bool(categories & {"증빙", "면담", "시설방문"})).lower(),
                "metric_impact": str(bool(categories & {"기준값/정량", "산식/기준산정", "실적기간"})).lower(),
                "department_candidate": action.get("department_candidate", ""),
                "source_id_4": atom.get("source_id_4", ""),
                "source_id_3": atom.get("source_id_3", ""),
                "top_candidate_source_id": top.get("candidate_source_id", ""),
                "top_candidate_score": top.get("score", ""),
                "recommended_next_step": recommended_next_step(atom, risk),
                "candidate_only_warning": "Review queue rows are operational triage candidates, not final judgments.",
            }
        )
    return sorted(rows, key=lambda row: (int(row["priority"]), row["cycle4_criterion"], row["section_type"], row["change_id"]))


def recommended_next_step(atom: dict[str, Any], risk: str) -> str:
    if is_manual_review_atom(atom):
        return "N:M 이동/분리 가능성이 큰 준거이므로 원문 대조 후 항목 단위 매핑 확정"
    if not atom.get("source_id_4"):
        return "4주기 전역 후보와 대조하여 삭제인지 이동인지 판정"
    if not atom.get("source_id_3"):
        return "3주기 전역 후보와 대조하여 신설인지 이동인지 판정"
    if risk == "high":
        return "부서 공지 전 공식 기준·증빙 범위 확인"
    return "담당부서 검토 후 준비과제 상태 확정"


def build_review_packets(
    atoms: list[dict[str, Any]],
    actions_by_change: dict[str, dict[str, Any]],
    matches_by_change: dict[str, list[dict[str, Any]]],
    mapping_rows: list[dict[str, Any]],
) -> None:
    REVIEW_PACKET_DIR.mkdir(parents=True, exist_ok=True)
    mappings_by_criterion: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in mapping_rows:
        for criterion in {row.get("cycle4_criterion", ""), row.get("cycle3_criterion", "")}:
            if criterion in MANUAL_REVIEW_CRITERIA:
                mappings_by_criterion[criterion].append(row)

    for criterion in sorted(MANUAL_REVIEW_CRITERIA):
        related = [
            atom
            for atom in atoms
            if atom.get("cycle4_criterion") == criterion or atom.get("cycle3_criterion") == criterion
        ]
        lines = [
            f"# 수동 검토 패킷: {criterion}",
            "",
            f"- Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- Related change atoms: {len(related)}",
            f"- Source-only rows: {sum(1 for atom in related if not atom.get('source_id_4'))}",
            f"- Target-only rows: {sum(1 for atom in related if not atom.get('source_id_3'))}",
            f"- Evidence/metric impact rows: {sum(1 for atom in related if set(filter(None, atom.get('change_categories', '').split(';'))) & HIGH_IMPACT_CATEGORIES)}",
            "",
            "## Mapping Candidates",
            "",
        ]
        if mappings_by_criterion[criterion]:
            for row in mappings_by_criterion[criterion]:
                lines.append(
                    f"- c4 {row.get('cycle4_criterion')} {row.get('cycle4_title')} <- "
                    f"c3 {row.get('cycle3_criterion')} {row.get('cycle3_title')} "
                    f"({row.get('verification_status')}, sim={row.get('title_similarity')})"
                )
        else:
            lines.append("- No canonical mapping candidates found.")

        lines.extend(["", "## Department Impact", ""])
        dept_counts = Counter(
            actions_by_change.get(atom["change_id"], {}).get("primary_department", "")
            for atom in related
        )
        for department, count in dept_counts.most_common():
            lines.append(f"- {department or '미지정'}: {count}")

        lines.extend(["", "## Change Review Rows", ""])
        for atom in related:
            action = actions_by_change.get(atom["change_id"], {})
            top_matches = matches_by_change.get(atom["change_id"], [])[:3]
            lines.extend(
                [
                    f"### {atom['change_id']} | {atom.get('section_type')} | {atom.get('change_type')} | {action.get('risk_level', '')}",
                    "",
                    f"- Review reason: {atom.get('review_reason', '')}",
                    f"- Global match: {atom.get('global_match_status', '')} ({atom.get('global_candidate_count', '0')} reportable candidates)",
                    f"- Departments: {action.get('department_candidate', '')}",
                    f"- Source IDs: 4주기 `{atom.get('source_id_4', '') or '-'}` / 3주기 `{atom.get('source_id_3', '') or '-'}`",
                    f"- 4주기 원문: {atom.get('source_text_4', '') or '-'}",
                    f"- 3주기 원문: {atom.get('source_text_3', '') or '-'}",
                ]
            )
            if top_matches:
                lines.append("- Global candidates:")
                for match in top_matches:
                    lines.append(
                        f"  - rank {match['rank']} score {match['score']}: "
                        f"{match['candidate_source_id']} / {match['candidate_text'][:180]}"
                    )
            lines.append("")

        path = REVIEW_PACKET_DIR / f"criterion_{criterion.replace('.', '_')}.md"
        path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def build_graph_exports(
    sources: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    matches_by_change: dict[str, list[dict[str, Any]]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: dict[str, dict[str, Any]] = {}

    def add_node(node_id: str, node_type: str, label: str, **props: Any) -> None:
        nodes.setdefault(
            node_id,
            {
                "node_id": node_id,
                "node_type": node_type,
                "label": label,
                **props,
            },
        )

    def add_edge(source: str, target: str, edge_type: str, **props: Any) -> None:
        if not source or not target:
            return
        edge_id = f"edge:{slug(edge_type)}:{slug(source)}:{slug(target)}"
        edges.setdefault(
            edge_id,
            {
                "edge_id": edge_id,
                "source_node_id": source,
                "target_node_id": target,
                "edge_type": edge_type,
                **props,
            },
        )

    for source in sources:
        criterion_id = f"criterion:c{source['cycle']}:{source['criterion']}"
        add_node(
            criterion_id,
            "Criterion",
            f"{source['cycle']}주기 {source['criterion']} {source['title']}",
            cycle=source["cycle"],
            criterion=source["criterion"],
            title=source["title"],
        )
        source_node_id = f"source:{source['source_id']}"
        node_type = "Evidence" if source.get("section_type") == "evidence" else "SourceItem"
        add_node(
            source_node_id,
            node_type,
            f"{source['cycle']}주기 {source['criterion']} {source.get('section_label', source.get('section_type', ''))}",
            source_id=source["source_id"],
            verification_status=source.get("verification_status", ""),
            cycle=source["cycle"],
            criterion=source["criterion"],
            section_type=source.get("section_type", ""),
            field_name=source.get("field_name", ""),
            content_hash=source.get("content_hash", ""),
        )
        add_edge(criterion_id, source_node_id, "requires")

    for atom in atoms:
        change_id = f"change:{atom['change_id']}"
        add_node(
            change_id,
            "ChangeAtom",
            f"{atom.get('cycle4_criterion') or atom.get('cycle3_criterion')} {atom.get('change_type')}",
            change_id=atom["change_id"],
            change_type=atom.get("change_type", ""),
            verification_status=atom.get("verification_status", ""),
            global_match_status=atom.get("global_match_status", ""),
        )
        for sid in [atom.get("source_id_4", ""), atom.get("source_id_3", "")]:
            if sid:
                add_edge(change_id, f"source:{sid}", "requires")
        if atom.get("source_id_4") and atom.get("source_id_3"):
            add_edge(f"source:{atom['source_id_4']}", f"source:{atom['source_id_3']}", "changed_from", change_id=atom["change_id"])
        for match in matches_by_change.get(atom["change_id"], [])[:1]:
            if atom.get("global_match_status") in {"strong_candidate", "possible_candidate", "weak_candidate"}:
                if match["candidate_direction"] == "c4_to_c3" and atom.get("source_id_4"):
                    add_edge(
                        f"source:{atom['source_id_4']}",
                        f"source:{match['candidate_source_id']}",
                        "moved_from",
                        change_id=atom["change_id"],
                        score=match["score"],
                    )
                elif match["candidate_direction"] == "c3_to_c4":
                    add_edge(
                        f"source:{match['candidate_source_id']}",
                        f"source:{atom.get('source_id_3', '')}",
                        "moved_from",
                        change_id=atom["change_id"],
                        score=match["score"],
                    )

    for action in actions:
        action_id = f"action:{action['action_id']}"
        add_node(
            action_id,
            "Action",
            f"{action.get('cycle4_criterion')} {action.get('action_type', action.get('change_type', ''))}",
            action_id=action["action_id"],
            priority=action.get("priority", ""),
            action_type=action.get("action_type", ""),
            verification_status=action.get("verification_status", ""),
        )
        add_edge(action_id, f"change:{action['change_id']}", "requires")
        risk_id = f"risk:{action.get('risk_level', 'unknown')}"
        add_node(risk_id, "Risk", action.get("risk_level", "unknown"), risk_level=action.get("risk_level", "unknown"))
        add_edge(action_id, risk_id, "has_risk")
        for department in [action.get("primary_department", "")] + list(filter(None, action.get("support_departments", "").split(";"))):
            if department:
                dept_id = f"department:{slug(department)}"
                add_node(dept_id, "Department", department, department=department)
                add_edge(action_id, dept_id, "owned_by")
        if action.get("evidence_link"):
            add_edge(action_id, f"source:{action['evidence_link']}", "needs_evidence")

    rag_chunks: list[dict[str, Any]] = []
    change_ids_by_source: dict[str, list[str]] = defaultdict(list)
    for atom in atoms:
        for sid in [atom.get("source_id_4", ""), atom.get("source_id_3", "")]:
            if sid:
                change_ids_by_source[sid].append(atom["change_id"])
    for source in sources:
        rag_chunks.append(
            {
                "chunk_id": f"chunk:{source['source_id']}",
                "source_id": source["source_id"],
                "verification_status": source.get("verification_status", ""),
                "text": source["content"],
                "metadata": {
                    "cycle": source["cycle"],
                    "criterion": source["criterion"],
                    "title": source["title"],
                    "section_type": source.get("section_type", ""),
                    "section_label": source.get("section_label", ""),
                    "field_name": source.get("field_name", ""),
                    "item_path": source.get("item_path", ""),
                    "source_kind": source.get("source_kind", ""),
                    "content_hash": source.get("content_hash", ""),
                    "linked_change_ids": sorted(set(change_ids_by_source.get(source["source_id"], []))),
                },
            }
        )

    return (
        sorted(nodes.values(), key=lambda row: row["node_id"]),
        sorted(edges.values(), key=lambda row: row["edge_id"]),
        rag_chunks,
    )


def build_dashboard_exports(
    atoms: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
) -> None:
    actions_by_change = {row["change_id"]: row for row in actions}
    criteria: dict[tuple[str, str], dict[str, Any]] = {}
    for atom in atoms:
        criterion = atom.get("cycle4_criterion") or atom.get("cycle3_criterion")
        title = atom.get("cycle4_title") or atom.get("cycle3_title")
        key = (criterion, title)
        row = criteria.setdefault(
            key,
            {
                "cycle4_criterion": criterion,
                "cycle4_title": title,
                "total_changes": 0,
                "confirmed_count": 0,
                "candidate_count": 0,
                "needs_review_count": 0,
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "official_confirmation_needed_count": 0,
                "manual_review_required": str(criterion in MANUAL_REVIEW_CRITERIA).lower(),
                "change_type_counts": Counter(),
                "primary_departments": Counter(),
            },
        )
        row["total_changes"] += 1
        row[f"{atom.get('verification_status')}_count"] += 1
        action = actions_by_change.get(atom["change_id"], {})
        if action.get("risk_level") == "high":
            row["high_risk_count"] += 1
        elif action.get("risk_level") == "medium":
            row["medium_risk_count"] += 1
        if atom.get("official_confirmation_needed") == "true":
            row["official_confirmation_needed_count"] += 1
        row["change_type_counts"][atom.get("change_type", "")] += 1
        if action.get("primary_department"):
            row["primary_departments"][action["primary_department"]] += 1

    criterion_summary: list[dict[str, Any]] = []
    for row in criteria.values():
        row["change_type_counts"] = ";".join(f"{key}:{value}" for key, value in row["change_type_counts"].most_common())
        row["primary_departments"] = ";".join(f"{key}:{value}" for key, value in row["primary_departments"].most_common())
        criterion_summary.append(row)
    criterion_summary.sort(key=lambda row: row["cycle4_criterion"])

    department_summary: dict[str, dict[str, Any]] = {}
    for action in actions:
        dept = action.get("primary_department") or "미지정"
        row = department_summary.setdefault(
            dept,
            {
                "primary_department": dept,
                "action_count": 0,
                "high_risk_count": 0,
                "medium_risk_count": 0,
                "official_confirmation_needed_count": 0,
                "criteria": set(),
                "action_type_counts": Counter(),
            },
        )
        row["action_count"] += 1
        if action.get("risk_level") == "high":
            row["high_risk_count"] += 1
        elif action.get("risk_level") == "medium":
            row["medium_risk_count"] += 1
        if action.get("official_confirmation_needed") == "true":
            row["official_confirmation_needed_count"] += 1
        if action.get("cycle4_criterion"):
            row["criteria"].add(action["cycle4_criterion"])
        row["action_type_counts"][action.get("action_type", "")] += 1

    department_rows: list[dict[str, Any]] = []
    for row in department_summary.values():
        row["criteria"] = ";".join(sorted(row["criteria"]))
        row["action_type_counts"] = ";".join(f"{key}:{value}" for key, value in row["action_type_counts"].most_common())
        department_rows.append(row)
    department_rows.sort(key=lambda row: (-row["high_risk_count"], row["primary_department"]))

    evidence_rows = [
        {
            "checklist_id": f"evidence_{idx:05d}",
            "action_id": action["action_id"],
            "change_id": action["change_id"],
            "cycle4_criterion": action.get("cycle4_criterion", ""),
            "cycle4_title": action.get("cycle4_title", ""),
            "section_type": action.get("section_type", ""),
            "field_or_focus": action.get("evidence_focus", ""),
            "primary_department": action.get("primary_department", ""),
            "support_departments": action.get("support_departments", ""),
            "data_period": action.get("data_period", ""),
            "metric_or_threshold": action.get("metric_or_threshold", ""),
            "evidence_link": action.get("evidence_link", ""),
            "official_confirmation_needed": action.get("official_confirmation_needed", ""),
            "preparation_task": action.get("preparation_task", ""),
        }
        for idx, action in enumerate(actions, start=1)
        if action.get("section_type") == "evidence"
        or any(token in action.get("evidence_focus", "") for token in ["증빙", "면담", "시설방문", "기준값", "산식", "실적기간"])
    ]

    high_risk_rows = [action for action in actions if action.get("risk_level") == "high"]

    write_dataset(DASHBOARD_DIR, "criterion_change_summary", criterion_summary)
    write_dataset(DASHBOARD_DIR, "manual_review_queue", review_queue)
    write_dataset(DASHBOARD_DIR, "department_action_summary", department_rows)
    write_dataset(DASHBOARD_DIR, "evidence_checklist", evidence_rows)
    write_dataset(DASHBOARD_DIR, "high_risk_items", high_risk_rows)


def write_operational_schema() -> None:
    schema = """# Operational Dataset Schema

Generated by `scripts/build_operational_datasets.py` from canonical outputs.

## Trust Boundary

- `canonical_source` remains the only source-verified text table.
- `global_match_candidate`, `review_queue`, enriched `change_atom`, enriched `department_action`, graph exports, and dashboard exports are operational candidates.
- `rag_chunks.text` is copied only from `canonical_source.content`.
- AI metadata remains isolated in `candidate_metadata`; this stage does not promote it to truth.

## Added/Generated Tables

- `global_match_candidate`: top-5 opposite-cycle source candidates for source-only, target-only, and low-similarity change atoms.
- `review_queue`: prioritized human review and official confirmation queue.
- `graph_nodes` / `graph_edges`: Graph RAG nodes and typed edges.
- `rag_chunks`: source-verified retrieval chunks with metadata and linked change IDs.
- `outputs/review_packets/criterion_*.md`: manual review packets for `1.5`, `3.4`, `4.2`, `4.3`.
- `outputs/dashboard_mvp/*`: CSV/JSONL tables for a dashboard MVP.

## Added Fields

- `change_atom`: `global_match_status`, `global_candidate_count`, `review_reason`, `human_review_status`, `official_confirmation_needed`.
- `department_action`: `action_type`, `primary_department`, `support_departments`, `data_period`, `metric_or_threshold`, `evidence_link`, `confirmed_by`, `confirmed_at`, `source_support_level`, `official_confirmation_needed`.
"""
    (DATA_DIR / "operational_schema.md").write_text(schema, encoding="utf-8")


def write_operational_qa_report(
    *,
    sources: list[dict[str, Any]],
    matches: list[dict[str, Any]],
    atoms: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    rag_chunks: list[dict[str, Any]],
) -> None:
    source_ids = {row["source_id"] for row in sources}
    change_ids = {row["change_id"] for row in atoms}
    action_change_ids = {row["change_id"] for row in actions}
    node_ids = {row["node_id"] for row in nodes}

    bad_matches = [
        row["match_id"]
        for row in matches
        if row["query_source_id"] not in source_ids
        or row["candidate_source_id"] not in source_ids
        or not row.get("score")
        or not row.get("match_reason")
    ]
    bad_confirmed = [
        row["change_id"]
        for row in atoms
        if row.get("verification_status") == "confirmed"
        and (row.get("change_type") != "유지" or (parse_similarity(row.get("similarity", "")) or 0.0) < 0.99)
    ]
    bad_manual = [
        row["change_id"]
        for row in atoms
        if is_manual_review_atom(row) and row.get("verification_status") == "confirmed"
    ]
    bad_actions = [
        row["action_id"]
        for row in actions
        if row["change_id"] not in change_ids or not (row.get("source_id_4") or row.get("source_id_3") or row.get("evidence_link"))
    ]
    bad_edges = [
        row["edge_id"]
        for row in edges
        if row["source_node_id"] not in node_ids or row["target_node_id"] not in node_ids
    ]
    bad_chunks = [
        row["chunk_id"]
        for row in rag_chunks
        if row.get("verification_status") != "source_verified" or row["source_id"] not in source_ids or not row.get("text")
    ]
    packet_paths = [REVIEW_PACKET_DIR / f"criterion_{criterion.replace('.', '_')}.md" for criterion in sorted(MANUAL_REVIEW_CRITERIA)]
    missing_packets = [str(path.relative_to(ROOT)) for path in packet_paths if not path.exists()]

    risk_counts = Counter(row.get("risk_level", "") for row in actions)
    global_status_counts = Counter(row.get("global_match_status", "") for row in atoms)

    lines = [
        "# Operational QA Report",
        "",
        f"- Generated: {dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Source rows: {len(sources)}",
        f"- Global match candidate rows: {len(matches)}",
        f"- Enriched change atom rows: {len(atoms)}",
        f"- Enriched department action rows: {len(actions)}",
        f"- Review queue rows: {len(review_queue)}",
        f"- Graph nodes: {len(nodes)}",
        f"- Graph edges: {len(edges)}",
        f"- RAG chunks: {len(rag_chunks)}",
        "",
        "## Distribution",
        "",
        f"- Global match status: {dict(global_status_counts)}",
        f"- Department action risk: {dict(risk_counts)}",
        "",
        "## QA Checks",
        "",
        f"- Global match refs/score/reason: {'PASS' if not bad_matches else 'CHECK ' + str(bad_matches[:10])}",
        f"- Confirmed changes are near-exact 유지 only: {'PASS' if not bad_confirmed else 'CHECK ' + str(bad_confirmed[:10])}",
        f"- N:M manual criteria remain needs_review: {'PASS' if not bad_manual else 'CHECK ' + str(bad_manual[:10])}",
        f"- Department actions trace to source/change: {'PASS' if not bad_actions else 'CHECK ' + str(bad_actions[:10])}",
        f"- Graph edge endpoints exist: {'PASS' if not bad_edges else 'CHECK ' + str(bad_edges[:10])}",
        f"- RAG chunks use source_verified text: {'PASS' if not bad_chunks else 'CHECK ' + str(bad_chunks[:10])}",
        f"- Manual review packets exist: {'PASS' if not missing_packets else 'CHECK ' + str(missing_packets)}",
        f"- All actions reference known change IDs: {'PASS' if action_change_ids <= change_ids else 'CHECK'}",
        "",
        "## Notes",
        "",
        "- Global matches are candidates for review, not final migration/deletion/newness judgments.",
        "- Official confirmation fields are intentionally blank until a human records confirmation.",
    ]
    (DATA_DIR / "operational_qa_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REVIEW_PACKET_DIR.mkdir(parents=True, exist_ok=True)
    DASHBOARD_DIR.mkdir(parents=True, exist_ok=True)

    sources = read_jsonl("canonical_source")
    mapping_rows = read_jsonl("canonical_mapping")
    change_rows = read_jsonl("change_atom")
    action_rows = read_jsonl("department_action")

    sources_by_id = {row["source_id"]: row for row in sources}
    sources_by_cycle: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for source in sources:
        sources_by_cycle[source["cycle"]].append(source)

    pairs = mapping_pairs(mapping_rows)
    global_matches, matches_by_change = build_global_matches(change_rows, sources_by_id, sources_by_cycle, pairs)
    change_rows = enrich_change_atoms(change_rows, matches_by_change)
    atoms_by_id = {row["change_id"]: row for row in change_rows}
    action_rows = enrich_department_actions(action_rows, atoms_by_id)
    actions_by_change = {row["change_id"]: row for row in action_rows}
    review_queue = build_review_queue(change_rows, actions_by_change, matches_by_change)

    build_review_packets(change_rows, actions_by_change, matches_by_change, mapping_rows)
    graph_nodes, graph_edges, rag_chunks = build_graph_exports(sources, change_rows, action_rows, matches_by_change)

    write_dataset(DATA_DIR, "global_match_candidate", global_matches)
    write_dataset(DATA_DIR, "change_atom", change_rows)
    write_dataset(DATA_DIR, "department_action", action_rows)
    write_dataset(DATA_DIR, "review_queue", review_queue)
    write_jsonl(DATA_DIR / "graph_nodes.jsonl", graph_nodes)
    write_jsonl(DATA_DIR / "graph_edges.jsonl", graph_edges)
    write_jsonl(DATA_DIR / "rag_chunks.jsonl", rag_chunks)
    build_dashboard_exports(change_rows, action_rows, review_queue)
    write_operational_schema()
    write_operational_qa_report(
        sources=sources,
        matches=global_matches,
        atoms=change_rows,
        actions=action_rows,
        review_queue=review_queue,
        nodes=graph_nodes,
        edges=graph_edges,
        rag_chunks=rag_chunks,
    )

    print(f"global_match_candidate: {len(global_matches)} rows")
    print(f"change_atom: {len(change_rows)} rows")
    print(f"department_action: {len(action_rows)} rows")
    print(f"review_queue: {len(review_queue)} rows")
    print(f"graph_nodes: {len(graph_nodes)} rows")
    print(f"graph_edges: {len(graph_edges)} rows")
    print(f"rag_chunks: {len(rag_chunks)} rows")
    print(f"review_packets: {len(MANUAL_REVIEW_CRITERIA)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
