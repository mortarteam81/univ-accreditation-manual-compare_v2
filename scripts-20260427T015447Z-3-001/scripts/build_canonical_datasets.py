#!/usr/bin/env python3
"""Build accreditation-prep datasets from verified handbook JSON.

The user's verification applies to handbook source content only. AI-produced
mapping metadata in the JSON files is preserved as candidate metadata and is not
treated as confirmed truth by this pipeline.
"""

from __future__ import annotations

import csv
import datetime as dt
import difflib
import hashlib
import json
import re
import unicodedata
from collections import Counter, defaultdict
from functools import lru_cache
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "편람원본json"
OUTPUT_DIR = ROOT / "outputs" / "canonical_datasets"

SECTION_BY_FILENAME = {
    "개요": "overview",
    "보고서": "report",
    "근거": "evidence",
    "주요 점검": "checkpoints",
    "유의사항": "notes",
}

SECTION_LABELS = {
    "overview": "편람 개요",
    "report": "보고서 주요 내용",
    "evidence": "근거자료",
    "checkpoints": "주요 점검사항",
    "notes": "유의사항 및 관련 정책",
}

EVIDENCE_FIELDS = [
    "정보공시",
    "제출자료_관련규정",
    "제출자료_첨부",
    "현지확인자료",
    "현지면담",
    "시설방문",
]

MANUAL_REVIEW_CRITERIA = {"1.5", "3.4", "4.2", "4.3"}

DEPARTMENT_RULES = [
    (re.compile(r"^1\.1$"), "기획처, 교무처"),
    (re.compile(r"^1\.2$"), "기획처, 감사부서"),
    (re.compile(r"^1\.3$"), "기획처, 재무회계팀"),
    (re.compile(r"^1\.4$"), "기획처, 성과관리 담당부서"),
    (re.compile(r"^1\.5$"), "기획처, 교무처, 교육혁신원, 취·창업지원부서"),
    (re.compile(r"^1\.6$"), "사회공헌 담당부서, 지역협력부서, 산학협력단"),
    (re.compile(r"^2\.[1-5]$"), "교무처, 교육과정 담당부서"),
    (re.compile(r"^2\.6$"), "교수학습지원센터"),
    (re.compile(r"^3\.[1-3]$"), "교무처, 교원인사 담당부서"),
    (re.compile(r"^3\.4$"), "연구처, 교무처"),
    (re.compile(r"^3\.[5-6]$"), "총무처, 직원인사 담당부서"),
    (re.compile(r"^4\.1$"), "학생처, 장학 담당부서"),
    (re.compile(r"^4\.2$"), "학생상담센터, 인권센터, 장애학생지원센터"),
    (re.compile(r"^4\.3$"), "진로·취창업지원센터"),
    (re.compile(r"^4\.4$"), "시설관리팀, 교무처"),
    (re.compile(r"^4\.5$"), "학생처, 생활관, 시설관리팀"),
    (re.compile(r"^4\.6$"), "도서관"),
]


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value or "")
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def compare_key(value: str) -> str:
    value = normalize_text(value).lower()
    value = re.sub(r"[^\w가-힣]", "", value)
    return value


def criterion_key(criterion: str) -> str:
    return criterion.replace(".", "_").replace(" ", "_")


def short_hash(value: str) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:10]


def detect_section(path: Path) -> str:
    name = unicodedata.normalize("NFKC", path.name)
    for marker, section_type in SECTION_BY_FILENAME.items():
        if marker in name:
            return section_type
    raise ValueError(f"Cannot infer section type from filename: {path}")


def source_file_date(path: Path) -> str:
    match = re.search(r"(20\d{6})", unicodedata.normalize("NFKC", path.name))
    if not match:
        return ""
    value = match.group(1)
    return f"{value[:4]}-{value[4:6]}-{value[6:8]}"


def make_source_id(cycle: str, criterion: str, section_type: str, item_path: str) -> str:
    cycle_prefix = "c4" if cycle == "4" else "c3"
    safe_path = re.sub(r"[^0-9A-Za-z가-힣_.:-]+", "_", item_path)
    return f"{cycle_prefix}__{criterion_key(criterion)}__{section_type}__{safe_path}"


def title_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, compare_key(a), compare_key(b)).ratio()


def content_similarity(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, compare_key(a), compare_key(b)).ratio()


def iter_json_files() -> list[tuple[str, Path]]:
    files = sorted(INPUT_DIR.glob("*.json"))
    return [(detect_section(path), path) for path in files]


def add_candidate(
    candidate_metadata: list[dict[str, Any]],
    *,
    candidate_type: str,
    section_type: str,
    source_file: Path,
    input_index: int,
    source_id: str = "",
    ai_group_id: Any = "",
    ai_theme: Any = "",
    ai_mapping_type: Any = "",
    ai_mapping_note: Any = "",
    cycle4_criterion: str = "",
    cycle4_title: str = "",
    cycle_context: str = "",
    criterion_context: str = "",
    title_context: str = "",
    json_path: str = "",
) -> None:
    note = normalize_text(str(ai_mapping_note or ""))
    if candidate_type != "group_metadata" and not note:
        return
    candidate_metadata.append(
        {
            "candidate_id": f"cand_{len(candidate_metadata) + 1:05d}",
            "candidate_type": candidate_type,
            "verification_status": "candidate",
            "candidate_only_warning": "AI metadata is not user-verified; use as a review hint only.",
            "section_type": section_type,
            "section_label": SECTION_LABELS[section_type],
            "source_file": str(source_file.relative_to(ROOT)),
            "source_file_date": source_file_date(source_file),
            "input_index": input_index,
            "json_path": json_path,
            "source_id": source_id,
            "ai_group_id": str(ai_group_id or ""),
            "ai_theme": str(ai_theme or ""),
            "ai_mapping_type": str(ai_mapping_type or ""),
            "ai_mapping_note": note,
            "cycle4_criterion": cycle4_criterion,
            "cycle4_title": cycle4_title,
            "cycle_context": cycle_context,
            "criterion_context": criterion_context,
            "title_context": title_context,
        }
    )


def append_occurrence(record: dict[str, Any], source_file: Path, input_index: int) -> None:
    file_name = str(source_file.relative_to(ROOT))
    files = set(filter(None, record.get("source_files", "").split(";")))
    files.add(file_name)
    positions = set(filter(None, record.get("input_positions", "").split(";")))
    positions.add(str(input_index))
    record["source_files"] = ";".join(sorted(files))
    record["input_positions"] = ";".join(sorted(positions, key=lambda x: int(x)))
    record["occurrence_count"] = str(len(positions))


def add_source(
    sources: dict[str, dict[str, Any]],
    qa_issues: list[str],
    *,
    cycle: str,
    criterion: str,
    title: str,
    section_type: str,
    item_path: str,
    content: str,
    source_file: Path,
    input_index: int,
    field_name: str = "",
    item_no: str = "",
    subitem_no: str = "",
    parent_source_id: str = "",
    source_kind: str = "",
    content_level: str = "",
    json_path: str = "",
) -> str:
    clean_content = normalize_text(content)
    if not clean_content:
        qa_issues.append(
            f"Empty content skipped: cycle={cycle}, criterion={criterion}, "
            f"section={section_type}, path={item_path}, file={source_file.name}"
        )
        return ""

    base_source_id = make_source_id(cycle, criterion, section_type, item_path)
    source_id = base_source_id
    if source_id in sources and sources[source_id]["content"] != clean_content:
        suffix = short_hash(clean_content)
        source_id = f"{base_source_id}__variant_{suffix}"
        qa_issues.append(
            f"Source ID content collision: {base_source_id}; variant stored as {source_id}"
        )

    if source_id not in sources:
        sources[source_id] = {
            "source_id": source_id,
            "verification_status": "source_verified",
            "cycle": cycle,
            "criterion": criterion,
            "title": title,
            "section_type": section_type,
            "section_label": SECTION_LABELS[section_type],
            "source_file_date": source_file_date(source_file),
            "json_path": json_path,
            "item_path": item_path,
            "field_name": field_name,
            "item_no": str(item_no),
            "subitem_no": str(subitem_no),
            "parent_source_id": parent_source_id,
            "source_kind": source_kind,
            "content_level": content_level,
            "content": clean_content,
            "content_hash": short_hash(clean_content),
            "source_files": "",
            "input_positions": "",
            "occurrence_count": "0",
        }
    append_occurrence(sources[source_id], source_file, input_index)
    return source_id


def extract_content_and_note(value: Any) -> tuple[str, str]:
    if isinstance(value, dict):
        return str(value.get("content", "")), str(value.get("mapping_note", ""))
    return str(value), ""


def normalize_cycle_object(
    obj: dict[str, Any],
    *,
    cycle: str,
    cycle_path: str,
    section_type: str,
    source_file: Path,
    input_index: int,
    sources: dict[str, dict[str, Any]],
    candidate_metadata: list[dict[str, Any]],
    qa_issues: list[str],
) -> list[dict[str, str]]:
    criterion = str(obj.get("criterion", ""))
    title = str(obj.get("title", ""))
    refs: list[dict[str, str]] = []

    add_candidate(
        candidate_metadata,
        candidate_type="cycle_partial_mapping_note",
        section_type=section_type,
        source_file=source_file,
        input_index=input_index,
        ai_mapping_note=obj.get("partial_mapping_note", ""),
        cycle_context=cycle,
        criterion_context=criterion,
        title_context=title,
        json_path=f"{cycle_path}.partial_mapping_note",
    )
    add_candidate(
        candidate_metadata,
        candidate_type="cycle_note",
        section_type=section_type,
        source_file=source_file,
        input_index=input_index,
        ai_mapping_note=obj.get("note", ""),
        cycle_context=cycle,
        criterion_context=criterion,
        title_context=title,
        json_path=f"{cycle_path}.note",
    )

    if section_type == "overview":
        source_id = add_source(
            sources,
            qa_issues,
            cycle=cycle,
            criterion=criterion,
            title=title,
            section_type=section_type,
            item_path="content",
            content=str(obj.get("content", "")),
            source_file=source_file,
            input_index=input_index,
            field_name="content",
            source_kind="overview_content",
            content_level="criterion",
            json_path=f"{cycle_path}.content",
        )
        if source_id:
            refs.append({"source_id": source_id, "content": sources[source_id]["content"]})
        return refs

    if section_type in {"report", "checkpoints", "notes"}:
        for idx, item in enumerate(obj.get("items", []) or [], start=1):
            content, note = extract_content_and_note(item)
            item_no = str(item.get("no", idx)) if isinstance(item, dict) else str(idx)
            item_path = f"item:{int(float(item_no)) if item_no.isdigit() else item_no}"
            source_kind = {
                "report": "report_item",
                "checkpoints": "check_item",
                "notes": "caution_policy_item",
            }[section_type]
            source_id = add_source(
                sources,
                qa_issues,
                cycle=cycle,
                criterion=criterion,
                title=title,
                section_type=section_type,
                item_path=item_path,
                content=content,
                source_file=source_file,
                input_index=input_index,
                field_name="items",
                item_no=item_no,
                source_kind=source_kind,
                content_level="item",
                json_path=f"{cycle_path}.items[{idx - 1}].content",
            )
            if source_id:
                refs.append({"source_id": source_id, "content": sources[source_id]["content"]})
                add_candidate(
                    candidate_metadata,
                    candidate_type="item_mapping_note",
                    section_type=section_type,
                    source_file=source_file,
                    input_index=input_index,
                    source_id=source_id,
                    ai_mapping_note=note,
                    cycle_context=cycle,
                    criterion_context=criterion,
                    title_context=title,
                    json_path=f"{cycle_path}.items[{idx - 1}].mapping_note",
                )
            if isinstance(item, dict):
                for sub_idx, sub_content in enumerate(item.get("sub_items", []) or [], start=1):
                    sub_path = f"{item_path}.sub:{sub_idx:03d}"
                    sub_source_id = add_source(
                        sources,
                        qa_issues,
                        cycle=cycle,
                        criterion=criterion,
                        title=title,
                        section_type=section_type,
                        item_path=sub_path,
                        content=str(sub_content),
                        source_file=source_file,
                        input_index=input_index,
                        field_name="sub_items",
                        item_no=item_no,
                        subitem_no=str(sub_idx),
                        parent_source_id=source_id,
                        source_kind="sub_item",
                        content_level="sub_item",
                        json_path=f"{cycle_path}.items[{idx - 1}].sub_items[{sub_idx - 1}]",
                    )
                    if sub_source_id:
                        refs.append(
                            {
                                "source_id": sub_source_id,
                                "content": sources[sub_source_id]["content"],
                            }
                        )
        return refs

    if section_type == "evidence":
        for field_name in EVIDENCE_FIELDS:
            for idx, value in enumerate(obj.get(field_name, []) or [], start=1):
                content, note = extract_content_and_note(value)
                item_path = f"{field_name}:{idx:03d}"
                source_id = add_source(
                    sources,
                    qa_issues,
                    cycle=cycle,
                    criterion=criterion,
                    title=title,
                    section_type=section_type,
                    item_path=item_path,
                    content=content,
                    source_file=source_file,
                    input_index=input_index,
                    field_name=field_name,
                    item_no=str(idx),
                    source_kind="evidence_item",
                    content_level="item",
                    json_path=f"{cycle_path}.{field_name}[{idx - 1}].content",
                )
                if source_id:
                    refs.append({"source_id": source_id, "content": sources[source_id]["content"]})
                    add_candidate(
                        candidate_metadata,
                        candidate_type="item_mapping_note",
                        section_type=section_type,
                        source_file=source_file,
                        input_index=input_index,
                        source_id=source_id,
                        ai_mapping_note=note,
                        cycle_context=cycle,
                        criterion_context=criterion,
                        title_context=title,
                        json_path=f"{cycle_path}.{field_name}[{idx - 1}].mapping_note",
                    )
                if isinstance(value, dict):
                    for sub_idx, sub_content in enumerate(value.get("sub_items", []) or [], start=1):
                        sub_source_id = add_source(
                            sources,
                            qa_issues,
                            cycle=cycle,
                            criterion=criterion,
                            title=title,
                            section_type=section_type,
                            item_path=f"{item_path}.sub:{sub_idx:03d}",
                            content=str(sub_content),
                            source_file=source_file,
                            input_index=input_index,
                            field_name=field_name,
                            item_no=str(idx),
                            subitem_no=str(sub_idx),
                            parent_source_id=source_id,
                            source_kind="sub_item",
                            content_level="sub_item",
                            json_path=f"{cycle_path}.{field_name}[{idx - 1}].sub_items[{sub_idx - 1}]",
                        )
                        if sub_source_id:
                            refs.append(
                                {
                                    "source_id": sub_source_id,
                                    "content": sources[sub_source_id]["content"],
                                }
                            )
        return refs

    raise ValueError(f"Unsupported section type: {section_type}")


def change_categories(text: str, section_type: str, field_name: str = "") -> list[str]:
    target = normalize_text(text)
    categories: set[str] = set()
    if re.search(r"기준값|[0-9]+(?:\.[0-9]+)?\s*(?:%|원|명|건|천원|시간|학점)", target):
        categories.add("기준값/정량")
    if re.search(r"최근\s*[0-9]+년|[0-9]+년\s*자료|기준연도|평가\s*시점|회계연도", target):
        categories.add("실적기간")
    if re.search(r"산출|비율|평균|수용률|충원율|확보율|환원율|강의료", target):
        categories.add("산식/기준산정")
    if section_type == "evidence" or re.search(r"증빙|자료|규정|첨부|정보공시|현지확인", target):
        categories.add("증빙")
    if field_name == "현지면담" or "면담" in target:
        categories.add("면담")
    if field_name == "시설방문" or "시설방문" in target or "방문" in target:
        categories.add("시설방문")
    if re.search(r"신설|추가|포함|의무|필수", target):
        categories.add("범위확장")
    if re.search(r"삭제|제외|폐지", target):
        categories.add("범위축소")
    return sorted(categories)


def infer_change_type(similarity: float | None, note: str = "") -> str:
    note_key = compare_key(note)
    if similarity is None:
        if "이동" in note_key:
            return "이동후보"
        if "삭제" in note_key:
            return "삭제후보"
        return "삭제/이동후보"
    if similarity >= 0.97:
        return "유지"
    if similarity >= 0.72:
        return "변경"
    return "신설후보"


def status_for_change(change_type: str, similarity: float | None, criterion: str) -> str:
    if criterion in MANUAL_REVIEW_CRITERIA:
        return "needs_review"
    if change_type == "유지" and similarity is not None and similarity >= 0.99:
        return "confirmed"
    if change_type == "변경":
        return "candidate"
    return "needs_review"


def extract_mapping_note_by_source(candidate_metadata: list[dict[str, Any]]) -> dict[str, str]:
    notes: dict[str, str] = defaultdict(str)
    for row in candidate_metadata:
        if row["candidate_type"] == "item_mapping_note" and row["source_id"]:
            if row["ai_mapping_note"]:
                notes[row["source_id"]] += " " + row["ai_mapping_note"]
    return notes


def build_mapping_rows(raw_groups: list[dict[str, Any]]) -> list[dict[str, Any]]:
    aggregated: dict[tuple[str, str], dict[str, Any]] = {}
    for group in raw_groups:
        c4 = group["cycle_4"]
        for c3 in group["cycle_3"]:
            key = (c4["criterion"], c3["criterion"])
            sim = title_similarity(c4["title"], c3["title"])
            row = aggregated.setdefault(
                key,
                {
                    "mapping_id": f"map__c4_{criterion_key(c4['criterion'])}__c3_{criterion_key(c3['criterion'])}",
                    "cycle4_criterion": c4["criterion"],
                    "cycle4_title": c4["title"],
                    "cycle3_criterion": c3["criterion"],
                    "cycle3_title": c3["title"],
                    "section_types": set(),
                    "raw_mapping_types": set(),
                    "raw_group_ids": set(),
                    "title_similarity_values": [],
                    "candidate_basis": set(),
                },
            )
            row["section_types"].add(group["section_type"])
            if group.get("mapping_type"):
                row["raw_mapping_types"].add(group["mapping_type"])
            if group.get("group_id") is not None:
                row["raw_group_ids"].add(str(group.get("group_id")))
            row["title_similarity_values"].append(sim)
            if c4["criterion"] == c3["criterion"]:
                row["candidate_basis"].add("same_criterion_number")
            if sim >= 0.97:
                row["candidate_basis"].add("near_exact_title_match")
            row["candidate_basis"].add("json_group_membership_unverified")

    final_rows: list[dict[str, Any]] = []
    for row in aggregated.values():
        sims = row.pop("title_similarity_values")
        avg_sim = sum(sims) / len(sims)
        same_criterion = row["cycle4_criterion"] == row["cycle3_criterion"]
        manual = row["cycle4_criterion"] in MANUAL_REVIEW_CRITERIA
        if same_criterion and avg_sim >= 0.97 and not manual:
            verification_status = "confirmed"
            confirmed_mapping_type = "same_criterion_number_and_near_exact_title"
        elif same_criterion and not manual:
            verification_status = "candidate"
            confirmed_mapping_type = ""
        else:
            verification_status = "needs_review"
            confirmed_mapping_type = ""
        row.update(
            {
                "section_types": ";".join(sorted(row["section_types"])),
                "raw_mapping_types": ";".join(sorted(row["raw_mapping_types"])),
                "raw_group_ids": ";".join(sorted(row["raw_group_ids"])),
                "title_similarity": f"{avg_sim:.3f}",
                "manual_review_required": str(manual or verification_status == "needs_review").lower(),
                "verification_status": verification_status,
                "confirmed_mapping_type": confirmed_mapping_type,
                "candidate_basis": ";".join(sorted(row["candidate_basis"])),
                "candidate_only_warning": "raw_mapping_types/raw_group_ids are AI metadata and were not user-verified.",
            }
        )
        final_rows.append(row)
    return sorted(final_rows, key=lambda r: (r["cycle4_criterion"], r["cycle3_criterion"]))


MIN_DIRECT_MATCH_SIMILARITY = 0.52


def optimal_change_atom_assignments(
    c4_items: list[dict[str, Any]],
    c3_items: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    section_type: str,
) -> dict[str, tuple[str, float | None]]:
    """Choose the best one-to-one source pairing for a raw group.

    A sequential greedy pass can consume a 3-cycle item for an earlier 4-cycle
    row even when a later row is a much stronger match. The dynamic program
    maximizes total similarity across the whole group before rows are emitted.
    """
    candidate_pools: list[list[tuple[str, float]]] = []
    for c4_item in c4_items:
        c4_src = sources[c4_item["source_id"]]
        candidates = c3_items
        if section_type == "evidence":
            same_field = [
                item
                for item in c3_items
                if sources[item["source_id"]]["field_name"] == c4_src["field_name"]
            ]
            if same_field:
                candidates = same_field
        scored = []
        for c3_item in candidates:
            sim = content_similarity(c4_item["content"], c3_item["content"])
            if sim >= MIN_DIRECT_MATCH_SIMILARITY:
                scored.append((c3_item["source_id"], sim))
        candidate_pools.append(sorted(scored, key=lambda item: item[1], reverse=True))

    @lru_cache(maxsize=None)
    def solve(index: int, used_key: tuple[str, ...]) -> tuple[float, tuple[tuple[str, float | None], ...]]:
        if index >= len(c4_items):
            return 0.0, ()
        used = set(used_key)
        best_score, tail = solve(index + 1, used_key)
        best_assignments = (("", None),) + tail
        for source_id, sim in candidate_pools[index]:
            if source_id in used:
                continue
            next_used = tuple(sorted([*used, source_id]))
            tail_score, tail_assignments = solve(index + 1, next_used)
            score = sim + tail_score + 0.0001
            if score > best_score:
                best_score = score
                best_assignments = ((source_id, sim),) + tail_assignments
        return best_score, best_assignments

    _score, assignments = solve(0, ())
    return {
        c4_item["source_id"]: assignments[index]
        for index, c4_item in enumerate(c4_items)
    }


def build_change_atoms(
    raw_groups: list[dict[str, Any]],
    sources: dict[str, dict[str, Any]],
    candidate_metadata: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    notes_by_source = extract_mapping_note_by_source(candidate_metadata)
    atoms: list[dict[str, Any]] = []

    for group in raw_groups:
        c4_items = group["source_refs_4"]
        c3_items = group["source_refs_3"]
        assignments = optimal_change_atom_assignments(
            c4_items,
            c3_items,
            sources,
            group["section_type"],
        )
        used_c3: set[str] = set()

        for c4_item in c4_items:
            c4_src = sources[c4_item["source_id"]]
            assigned_source_id, best_sim = assignments.get(c4_item["source_id"], ("", None))

            if not assigned_source_id or best_sim is None:
                change_type = "신설후보"
                source_id_3 = ""
                source_text_3 = ""
                sim_value: float | None = None
            else:
                source_id_3 = assigned_source_id
                source_text_3 = sources[source_id_3]["content"]
                used_c3.add(source_id_3)
                sim_value = best_sim
                change_type = infer_change_type(best_sim)

            categories = change_categories(
                c4_item["content"] + " " + source_text_3,
                group["section_type"],
                c4_src.get("field_name", ""),
            )
            status = status_for_change(change_type, sim_value, group["cycle_4"]["criterion"])
            atom_id = f"chg_{len(atoms) + 1:05d}"
            atoms.append(
                {
                    "change_id": atom_id,
                    "verification_status": status,
                    "change_type": change_type,
                    "change_categories": ";".join(categories),
                    "similarity": "" if sim_value is None else f"{sim_value:.3f}",
                    "section_type": group["section_type"],
                    "section_label": SECTION_LABELS[group["section_type"]],
                    "cycle4_criterion": group["cycle_4"]["criterion"],
                    "cycle4_title": group["cycle_4"]["title"],
                    "cycle3_criterion": sources[source_id_3]["criterion"] if source_id_3 else "",
                    "cycle3_title": sources[source_id_3]["title"] if source_id_3 else "",
                    "source_id_4": c4_item["source_id"],
                    "source_id_3": source_id_3,
                    "source_text_4": c4_item["content"],
                    "source_text_3": source_text_3,
                    "field_name_4": c4_src.get("field_name", ""),
                    "item_path_4": c4_src.get("item_path", ""),
                    "candidate_note_3": notes_by_source.get(source_id_3, "").strip(),
                    "candidate_note_4": notes_by_source.get(c4_item["source_id"], "").strip(),
                    "manual_review_required": str(status == "needs_review").lower(),
                    "candidate_only_warning": "Change type is heuristic unless verification_status is confirmed.",
                }
            )

        for c3_item in c3_items:
            if c3_item["source_id"] in used_c3:
                continue
            c3_src = sources[c3_item["source_id"]]
            note = notes_by_source.get(c3_item["source_id"], "")
            change_type = infer_change_type(None, note)
            categories = change_categories(c3_item["content"], group["section_type"], c3_src.get("field_name", ""))
            atoms.append(
                {
                    "change_id": f"chg_{len(atoms) + 1:05d}",
                    "verification_status": "needs_review",
                    "change_type": change_type,
                    "change_categories": ";".join(categories),
                    "similarity": "",
                    "section_type": group["section_type"],
                    "section_label": SECTION_LABELS[group["section_type"]],
                    "cycle4_criterion": group["cycle_4"]["criterion"],
                    "cycle4_title": group["cycle_4"]["title"],
                    "cycle3_criterion": c3_src["criterion"],
                    "cycle3_title": c3_src["title"],
                    "source_id_4": "",
                    "source_id_3": c3_item["source_id"],
                    "source_text_4": "",
                    "source_text_3": c3_item["content"],
                    "field_name_4": "",
                    "item_path_4": "",
                    "candidate_note_3": note.strip(),
                    "candidate_note_4": "",
                    "manual_review_required": "true",
                    "candidate_only_warning": "Unmatched 3-cycle item requires human deletion/move review.",
                }
            )

    return atoms


def department_for(criterion: str) -> str:
    for pattern, department in DEPARTMENT_RULES:
        if pattern.match(criterion):
            return department
    return "기획처, 평가인증 총괄부서"


def action_risk(change_atom: dict[str, Any]) -> str:
    categories = set(filter(None, change_atom["change_categories"].split(";")))
    if change_atom["verification_status"] == "needs_review":
        return "high"
    high_cats = {"기준값/정량", "산식/기준산정", "증빙", "면담", "시설방문"}
    if categories & high_cats and change_atom["change_type"] != "유지":
        return "high"
    if change_atom["change_type"] in {"신설후보", "삭제후보", "이동후보", "삭제/이동후보"}:
        return "high"
    if change_atom["change_type"] == "변경":
        return "medium"
    return "low"


def build_department_actions(change_atoms: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for atom in change_atoms:
        if atom["change_type"] == "유지" and atom["verification_status"] == "confirmed":
            continue
        criterion = atom["cycle4_criterion"] or atom["cycle3_criterion"]
        risk = action_risk(atom)
        source_text = atom["source_text_4"] or atom["source_text_3"]
        categories = set(filter(None, atom["change_categories"].split(";")))
        benchmark = (
            criterion in {"1.6", "2.1", "2.2", "2.3", "4.2", "4.3", "4.5", "4.6"}
            and risk in {"high", "medium"}
        )
        evidence_focus = ";".join(
            sorted(categories & {"증빙", "면담", "시설방문", "기준값/정량", "산식/기준산정", "실적기간"})
        )
        if not evidence_focus:
            evidence_focus = "관련 규정·운영자료·실적자료 확인"
        actions.append(
            {
                "action_id": f"act_{len(actions) + 1:05d}",
                "change_id": atom["change_id"],
                "verification_status": atom["verification_status"],
                "risk_level": risk,
                "priority": {"high": "1", "medium": "2", "low": "3"}[risk],
                "cycle4_criterion": atom["cycle4_criterion"],
                "cycle4_title": atom["cycle4_title"],
                "section_type": atom["section_type"],
                "change_type": atom["change_type"],
                "department_candidate": department_for(criterion),
                "notice_required": str(risk in {"high", "medium"}).lower(),
                "benchmark_required": str(benchmark).lower(),
                "evidence_focus": evidence_focus,
                "preparation_task": f"{SECTION_LABELS[atom['section_type']]} 항목 검토 및 준비: {source_text}",
                "source_id_4": atom["source_id_4"],
                "source_id_3": atom["source_id_3"],
                "candidate_only_warning": "Department/risk values are operational candidates for review.",
            }
        )
    return actions


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_dataset(name: str, rows: list[dict[str, Any]]) -> None:
    write_jsonl(OUTPUT_DIR / f"{name}.jsonl", rows)
    write_csv(OUTPUT_DIR / f"{name}.csv", rows)


def write_schema_doc() -> None:
    schema = """# Canonical Dataset Schema

Generated from `편람원본json/*.json`.

## Trust Boundary

- `canonical_source`: user-verified handbook source content only.
- `candidate_metadata`: unverified AI metadata (`mapping_note`, `mapping_type`, `group_id`, `theme`) and item-level AI notes.
- `canonical_mapping`: mapping candidates generated from source criteria/title patterns and unverified group membership. Only rows marked `confirmed` should be treated as provisionally safe.
- `change_atom`: heuristic item-level change candidates. Only exact/high-confidence 유지 rows are `confirmed`; all others need review.
- `department_action`: operational candidates derived from change atoms.

## ID Rule

`source_id = cycle + criterion + section_type + item_path`

Example: `c4__1_1__report__item:1`

## Section Types

- `overview`
- `report`
- `evidence`
- `checkpoints`
- `notes`
"""
    (OUTPUT_DIR / "schema.md").write_text(schema, encoding="utf-8")


def write_qa_report(
    *,
    file_lengths: dict[str, int],
    sources: list[dict[str, Any]],
    candidate_metadata: list[dict[str, Any]],
    mappings: list[dict[str, Any]],
    change_atoms: list[dict[str, Any]],
    actions: list[dict[str, Any]],
    qa_issues: list[str],
) -> None:
    now = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    criteria_by_section: dict[str, set[str]] = defaultdict(set)
    for row in sources:
        if row["cycle"] == "4":
            criteria_by_section[row["section_type"]].add(row["criterion"])

    status_counts = Counter(row["verification_status"] for row in change_atoms)
    change_counts = Counter(row["change_type"] for row in change_atoms)
    risk_counts = Counter(row["risk_level"] for row in actions)
    mapping_status_counts = Counter(row["verification_status"] for row in mappings)

    metadata_leak_keys = {"mapping_note", "mapping_type", "group_id", "theme"}
    leaked = [row["source_id"] for row in sources if metadata_leak_keys & set(row.keys())]
    missing_content = [row["source_id"] for row in sources if not row.get("content")]
    bad_change_atoms = [
        row["change_id"] for row in change_atoms if not row.get("source_text_3") and not row.get("source_text_4")
    ]

    lines = [
        "# QA Report",
        "",
        f"- Generated: {now}",
        f"- Input JSON files: {len(file_lengths)}",
        f"- Canonical source rows: {len(sources)}",
        f"- Candidate metadata rows: {len(candidate_metadata)}",
        f"- Canonical mapping rows: {len(mappings)}",
        f"- Change atom rows: {len(change_atoms)}",
        f"- Department action rows: {len(actions)}",
        "",
        "## Input Completeness",
        "",
    ]
    for path, length in sorted(file_lengths.items()):
        status = "PASS" if length == 24 else "CHECK"
        lines.append(f"- {status}: `{path}` has {length} groups")

    lines.extend(["", "## 4-Cycle Criterion Coverage", ""])
    for section_type in sorted(SECTION_LABELS):
        count = len(criteria_by_section[section_type])
        status = "PASS" if count == 24 else "CHECK"
        lines.append(f"- {status}: `{section_type}` has {count}/24 4-cycle criteria")

    lines.extend(
        [
            "",
            "## Status Distribution",
            "",
            f"- Mapping verification: {dict(mapping_status_counts)}",
            f"- Change verification: {dict(status_counts)}",
            f"- Change types: {dict(change_counts)}",
            f"- Department action risk: {dict(risk_counts)}",
            "",
            "## Trust Boundary Checks",
            "",
            f"- AI metadata keys in canonical_source: {'PASS' if not leaked else 'CHECK ' + str(leaked[:10])}",
            f"- Missing canonical source content: {'PASS' if not missing_content else 'CHECK ' + str(missing_content[:10])}",
            f"- Change atoms without any source text: {'PASS' if not bad_change_atoms else 'CHECK ' + str(bad_change_atoms[:10])}",
            "- Manual review criteria fixed: `1.5`, `3.4`, `4.2`, `4.3`",
            "",
            "## Issues",
            "",
        ]
    )
    if qa_issues:
        lines.extend(f"- {issue}" for issue in qa_issues)
    else:
        lines.append("- No source extraction issues detected.")

    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- `mapping_note`, `mapping_type`, `group_id`, and `theme` are preserved only in `candidate_metadata` or explicitly candidate fields.",
            "- Non-confirmed mapping/change rows must be reviewed before being used as final accreditation judgments.",
        ]
    )
    (OUTPUT_DIR / "qa_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    if not INPUT_DIR.exists():
        raise SystemExit(f"Input directory does not exist: {INPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    sources: dict[str, dict[str, Any]] = {}
    candidate_metadata: list[dict[str, Any]] = []
    raw_groups: list[dict[str, Any]] = []
    file_lengths: dict[str, int] = {}
    qa_issues: list[str] = []

    for section_type, path in iter_json_files():
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"Expected top-level array in {path}")
        file_lengths[str(path.relative_to(ROOT))] = len(data)
        if len(data) != 24:
            qa_issues.append(f"Expected 24 groups in {path.name}, found {len(data)}")

        for input_index, group in enumerate(data, start=1):
            c4 = group.get("cycle_4", {})
            c3_list = group.get("cycle_3", []) or []
            add_candidate(
                candidate_metadata,
                candidate_type="group_metadata",
                section_type=section_type,
                source_file=path,
                input_index=input_index,
                ai_group_id=group.get("group_id", ""),
                ai_theme=group.get("theme", ""),
                ai_mapping_type=group.get("mapping_type", ""),
                ai_mapping_note=group.get("mapping_note", ""),
                cycle4_criterion=str(c4.get("criterion", "")),
                cycle4_title=str(c4.get("title", "")),
                json_path="$",
            )

            refs_4 = normalize_cycle_object(
                c4,
                cycle="4",
                cycle_path="cycle_4",
                section_type=section_type,
                source_file=path,
                input_index=input_index,
                sources=sources,
                candidate_metadata=candidate_metadata,
                qa_issues=qa_issues,
            )
            refs_3: list[dict[str, str]] = []
            for c3_index, c3 in enumerate(c3_list):
                refs_3.extend(
                    normalize_cycle_object(
                        c3,
                        cycle="3",
                        cycle_path=f"cycle_3[{c3_index}]",
                        section_type=section_type,
                        source_file=path,
                        input_index=input_index,
                        sources=sources,
                        candidate_metadata=candidate_metadata,
                        qa_issues=qa_issues,
                    )
                )
            raw_groups.append(
                {
                    "section_type": section_type,
                    "source_file": str(path.relative_to(ROOT)),
                    "input_index": input_index,
                    "group_id": group.get("group_id", ""),
                    "theme": group.get("theme", ""),
                    "mapping_type": group.get("mapping_type", ""),
                    "cycle_4": {
                        "criterion": str(c4.get("criterion", "")),
                        "title": str(c4.get("title", "")),
                    },
                    "cycle_3": [
                        {
                            "criterion": str(c3.get("criterion", "")),
                            "title": str(c3.get("title", "")),
                        }
                        for c3 in c3_list
                    ],
                    "source_refs_4": refs_4,
                    "source_refs_3": refs_3,
                }
            )

    source_rows = sorted(sources.values(), key=lambda r: (r["cycle"], r["criterion"], r["section_type"], r["item_path"]))
    mapping_rows = build_mapping_rows(raw_groups)
    change_atoms = build_change_atoms(raw_groups, sources, candidate_metadata)
    department_actions = build_department_actions(change_atoms)

    write_dataset("canonical_source", source_rows)
    write_dataset("candidate_metadata", candidate_metadata)
    write_dataset("canonical_mapping", mapping_rows)
    write_dataset("change_atom", change_atoms)
    write_dataset("department_action", department_actions)
    write_schema_doc()
    write_qa_report(
        file_lengths=file_lengths,
        sources=source_rows,
        candidate_metadata=candidate_metadata,
        mappings=mapping_rows,
        change_atoms=change_atoms,
        actions=department_actions,
        qa_issues=qa_issues,
    )

    print(f"Wrote datasets to {OUTPUT_DIR}")
    print(f"canonical_source rows: {len(source_rows)}")
    print(f"candidate_metadata rows: {len(candidate_metadata)}")
    print(f"canonical_mapping rows: {len(mapping_rows)}")
    print(f"change_atom rows: {len(change_atoms)}")
    print(f"department_action rows: {len(department_actions)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
