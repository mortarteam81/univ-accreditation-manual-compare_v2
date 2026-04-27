# QA Report

- Generated: 2026-04-27 10:37:14
- Input JSON files: 5
- Canonical source rows: 1634
- Candidate metadata rows: 585
- Canonical mapping rows: 34
- Change atom rows: 993
- Department action rows: 638

## Input Completeness

- PASS: `편람원본json/[검증완료]3주기, 4주기 편람 개요 비교(20260417).json` has 24 groups
- PASS: `편람원본json/[검증완료]3주기, 4주기 편람 근거 자료 비교(20260420).json` has 24 groups
- PASS: `편람원본json/[검증완료]3주기, 4주기 편람 보고서 주요 내용 비교(20260417).json` has 24 groups
- PASS: `편람원본json/[검증완료]3주기, 4주기 편람 유의사항 및 관련 정책 비교(20260422).json` has 24 groups
- PASS: `편람원본json/[검증완료]3주기, 4주기 편람 주요 점검사항 비교(20260421).json` has 24 groups

## 4-Cycle Criterion Coverage

- PASS: `checkpoints` has 24/24 4-cycle criteria
- PASS: `evidence` has 24/24 4-cycle criteria
- PASS: `notes` has 24/24 4-cycle criteria
- PASS: `overview` has 24/24 4-cycle criteria
- PASS: `report` has 24/24 4-cycle criteria

## Status Distribution

- Mapping verification: {'candidate': 4, 'needs_review': 18, 'confirmed': 12}
- Change verification: {'needs_review': 514, 'candidate': 124, 'confirmed': 355}
- Change types: {'신설후보': 269, '삭제/이동후보': 74, '변경': 162, '유지': 421, '이동후보': 23, '삭제후보': 44}
- Department action risk: {'high': 578, 'medium': 60}

## Trust Boundary Checks

- AI metadata keys in canonical_source: PASS
- Missing canonical source content: PASS
- Change atoms without any source text: PASS
- Manual review criteria fixed: `1.5`, `3.4`, `4.2`, `4.3`

## Issues

- Source ID content collision: c3__4_2__report__item:2; variant stored as c3__4_2__report__item:2__variant_17ec61ee0a
- Source ID content collision: c3__4_2__report__item:2.sub:001; variant stored as c3__4_2__report__item:2.sub:001__variant_154cf663e5

## Notes

- `mapping_note`, `mapping_type`, `group_id`, and `theme` are preserved only in `candidate_metadata` or explicitly candidate fields.
- Non-confirmed mapping/change rows must be reviewed before being used as final accreditation judgments.
