"""DB 임포트 검증 스크립트"""
import sqlite3, sys
from pathlib import Path

sys.stdout.reconfigure(encoding='utf-8')

DB = Path(__file__).parent / "accreditation_review.db"
conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row

print("=== 1. 섹션별 변경 통계 ===")
for r in conn.execute("SELECT * FROM v_section_change_stats"):
    print(f"  {dict(r)}")

print("\n=== 2. 부서별 업무량 ===")
for r in conn.execute("SELECT * FROM v_department_workload"):
    print(f"  {dict(r)}")

print("\n=== 3. DB 객체 목록 ===")
for r in conn.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY type, name"):
    print(f"  [{r['type']}] {r['name']}")

print("\n=== 4. 매핑 현황 ===")
for r in conn.execute("SELECT * FROM v_mapping_overview LIMIT 5"):
    print(f"  {dict(r)}")

print("\n=== 5. 고위험 검토 대기열 (상위 3건) ===")
for r in conn.execute("SELECT review_id, priority, cycle4_criterion, cycle4_title, change_type, global_match_status, top_candidate_score FROM v_high_priority_review LIMIT 3"):
    print(f"  {dict(r)}")

# 데이터 무결성 체크
print("\n=== 6. 데이터 무결성 체크 ===")
# change_atom.source_id_3/4 → canonical_source.source_id
orphan3 = conn.execute("""
    SELECT COUNT(*) FROM change_atom 
    WHERE source_id_3 != '' AND source_id_3 NOT IN (SELECT source_id FROM canonical_source)
""").fetchone()[0]
orphan4 = conn.execute("""
    SELECT COUNT(*) FROM change_atom 
    WHERE source_id_4 != '' AND source_id_4 NOT IN (SELECT source_id FROM canonical_source)
""").fetchone()[0]
print(f"  change_atom → canonical_source 연결 실패 (3주기): {orphan3}건")
print(f"  change_atom → canonical_source 연결 실패 (4주기): {orphan4}건")

# review_queue.change_id → change_atom.change_id
orphan_rq = conn.execute("""
    SELECT COUNT(*) FROM review_queue 
    WHERE change_id NOT IN (SELECT change_id FROM change_atom)
""").fetchone()[0]
print(f"  review_queue → change_atom 연결 실패: {orphan_rq}건")

# department_action.change_id → change_atom.change_id
orphan_da = conn.execute("""
    SELECT COUNT(*) FROM department_action 
    WHERE change_id NOT IN (SELECT change_id FROM change_atom)
""").fetchone()[0]
print(f"  department_action → change_atom 연결 실패: {orphan_da}건")

print("\n✅ 검증 완료")
conn.close()
