# Canonical Dataset Schema

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
