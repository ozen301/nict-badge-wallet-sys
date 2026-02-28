# v1.0.0 Migration Guide

This release is a hard-break semantic refactor.

Core semantics in `v1.0.0`:
- `NFTDefinition` = definition metadata (row in `nfts`)
- `NFTInstance` = issued/owned instance (row in `user_nft_ownership`)
- prize draws evaluate `NFTInstance` records, not definitions

## Breaking API Changes

### Model exports
- Removed canonical export: `NFT`
- Removed canonical export: `UserNFTOwnership`
- Use instead: `NFTDefinition`, `NFTInstance`
- `NFTTemplate` remains available

### Method renames
- `NFT.issue_dbwise_to(...)` -> `NFTDefinition.issue_dbwise_to_user(...)`
- `NFT.count_nfts_by_prefix(...)` -> `NFTDefinition.count_instances_by_prefix(...)`
- `UserNFTOwnership.get_by_user_and_nft(...)` -> `NFTInstance.get_by_user_and_definition(...)`
- `User.unlock_cells_for_nft(...)` -> `User.unlock_cells_for_definition(...)`

### NFTInstance API changes
- `NFTInstance.nft_id` -> `NFTInstance.definition_id`
- `NFTInstance.nft` -> `NFTInstance.definition`

### NFTCouponBinding API changes
- `NFTCouponBinding.nft_id` -> `NFTCouponBinding.definition_id`
- `NFTCouponBinding.nft` -> `NFTCouponBinding.definition`
- `NFTCouponBinding.get_active_for_nft(session, definition_id)` keeps method name, but now expects `definition_id`.
- `NFTCouponBinding.get_binding(session, definition_id, template_id)` now expects `definition_id`.

### CouponInstance API changes
- `CouponInstance.nft_id` -> `CouponInstance.definition_id`
- `CouponInstance.display_nft_id` -> `CouponInstance.display_definition_id`
- `CouponInstance.nft` -> `CouponInstance.definition`
- `CouponInstance.display_nft` -> `CouponInstance.display_definition`

### CouponTemplate and CouponStore API changes
- `CouponTemplate.default_display_nft_id` -> `CouponTemplate.default_display_definition_id`
- `CouponStore.nft_id` -> `CouponStore.definition_id`
- `CouponStore.nft` -> `CouponStore.definition`

### NFTClaimRequest API changes
- `NFTClaimRequest.nft_id` -> `NFTClaimRequest.definition_id`
- `NFTClaimRequest.nft` -> `NFTClaimRequest.definition`

### Workflow signature changes
- `create_and_issue_nft(..., nft_template=...)` -> `create_and_issue_nft(..., definition_or_template=...)`
- `create_and_issue_nft(...)` return type:
  - old mental model: definition-like
  - `v1.0.0`: returns `NFTInstance`

- `run_prize_draw(session, nft=..., ...)` -> `run_prize_draw(session, instance=..., ...)`
- `run_prize_draw_batch(..., nfts=[...])` -> `run_prize_draw_batch(..., instances=[...])`
- `run_final_attendance_prize_draw(..., attendance_template_id=...)` ->
  `run_final_attendance_prize_draw(..., attendance_definition_id=...)`

### PrizeDrawResult API changes
- `PrizeDrawResult.nft_id` -> `PrizeDrawResult.definition_id`
- `PrizeDrawResult.nft` -> `PrizeDrawResult.definition`

### Bingo API naming changes
- `BingoCell.target_template_id` -> `BingoCell.target_definition_id`
- `BingoCell.target_template` -> `BingoCell.target_definition`
- `BingoCell.nft_id` -> `BingoCell.definition_id`
- `BingoCell.nft` -> `BingoCell.definition`
- `BingoCell.to_json()` key changed:
  - old: `nft_id`
  - new: `definition_id`
  - old: `target_template`
  - new: `target_definition`
- `BingoCard.generate_for_user(...)` args:
  - `center_template` -> `center_definition`
  - `included_templates` -> `included_definitions`
  - `excluded_templates` -> `excluded_definitions`
- `BingoCardIssueTask.center_nft_id` -> `BingoCardIssueTask.center_definition_id`
- `PreGeneratedBingoCard.center_nft_id` -> `PreGeneratedBingoCard.center_definition_id`
- `PreGeneratedBingoCard.cell_nft_ids` -> `PreGeneratedBingoCard.cell_definition_ids`

## Behavioral Changes

### User holdings
- `User.nfts` now returns NFT instances (`list[NFTInstance]`), not definitions.
- Access definition fields via `instance.definition`.

### Prize draw evaluation
- Draw number is derived from `NFTInstance.nft_origin` on the supplied instance.
- `PrizeDrawResult.ownership_id` is the primary semantic reference to the evaluated instance.

### Temporary schema guard (important)
Schema is intentionally unchanged in this release. Because `prize_draw_results` is still unique on `(nft_id, draw_type_id)`, evaluating multiple instances of the same definition in the same draw cannot be stored independently yet.

Current behavior in `v1.0.0`:
- The workflow raises `ValueError` instead of silently overwriting rows.

Follow-up schema plan is documented in:
- [docs/schema_followup_memo.md](./schema_followup_memo.md)

## Quick Before/After

### Imports
```python
# before
from nictbw.models import NFT, UserNFTOwnership

# after
from nictbw.models import NFTDefinition, NFTInstance
```

### Issue and retrieve ownership
```python
# before
nft = NFT.get_by_prefix(session, "ABC")
ownership = nft.issue_dbwise_to(session, user)
ownership = UserNFTOwnership.get_by_user_and_nft(session, user, nft)

# after
definition = NFTDefinition.get_by_prefix(session, "ABC")
instance = definition.issue_dbwise_to_user(session, user)
instance = NFTInstance.get_by_user_and_definition(session, user, definition)
```

### Run draw
```python
# before
result = run_prize_draw(session, nft, draw_type)

# after
result = run_prize_draw(session, instance, draw_type)
```

## Upgrade Checklist
1. Update imports and renamed method calls.
2. Update workflow call arguments (`definition_or_template`, `instances`, `attendance_definition_id`).
3. Update bingo JSON consumers (`target_definition` key).
4. Re-run your integration tests against `v1.0.0`.
