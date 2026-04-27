# Operational QA Report

- Generated: 2026-04-27 10:37:30
- Source rows: 1634
- Global match candidate rows: 2050
- Enriched change atom rows: 993
- Enriched department action rows: 638
- Review queue rows: 652
- Graph nodes: 3346
- Graph edges: 7570
- RAG chunks: 1634

## Distribution

- Global match status: {'weak_candidate': 202, 'possible_candidate': 68, 'not_applicable': 583, 'strong_candidate': 46, 'no_candidate': 94}
- Department action risk: {'high': 481, 'medium': 157}

## QA Checks

- Global match refs/score/reason: PASS
- Confirmed changes are near-exact 유지 only: PASS
- N:M manual criteria remain needs_review: PASS
- Department actions trace to source/change: PASS
- Graph edge endpoints exist: PASS
- RAG chunks use source_verified text: PASS
- Manual review packets exist: PASS
- All actions reference known change IDs: PASS

## Notes

- Global matches are candidates for review, not final migration/deletion/newness judgments.
- Official confirmation fields are intentionally blank until a human records confirmation.
