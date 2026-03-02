"""stage 3 full semantic rename

Breaking migration for v1.1.0 schema alignment.

- Drop legacy unique constraints:
  - uq_prize_draw_result_unique (prize_draw_results.nft_id, draw_type_id)
  - uq_user_nft_once (user_nft_ownership.user_id, nft_id)
- Rename tables:
  - nfts -> nft_definitions
  - user_nft_ownership -> nft_instances
- Rename columns across dependent tables to definition-/instance-first naming.
- Rename affected FK constraints and indexes for consistency.
- Rename remaining unique constraint:
  - bingo_card_issue_tasks_ownership_id_key -> bingo_card_issue_tasks_nft_instance_id_key

Revision ID: b6f3e4c9d8a1
Revises: a1b2c3d4e5f6
Create Date: 2026-03-02 19:15:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b6f3e4c9d8a1"
down_revision: Union[str, Sequence[str], None] = "a1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _drop_constraint_if_exists(table_name: str, constraint_name: str, constraint_type: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = current_schema()
                  AND t.relname = '{table_name}'
                  AND c.conname = '{constraint_name}'
            ) THEN
                EXECUTE 'ALTER TABLE {table_name} DROP CONSTRAINT {constraint_name}';
            END IF;
        END
        $$;
        """
    )


def _rename_constraint_if_exists(table_name: str, old_name: str, new_name: str) -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class t ON t.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = t.relnamespace
                WHERE n.nspname = current_schema()
                  AND t.relname = '{table_name}'
                  AND c.conname = '{old_name}'
            ) THEN
                EXECUTE 'ALTER TABLE {table_name} RENAME CONSTRAINT {old_name} TO {new_name}';
            END IF;
        END
        $$;
        """
    )


def _rename_index_if_exists(old_name: str, new_name: str) -> None:
    op.execute(f"ALTER INDEX IF EXISTS {old_name} RENAME TO {new_name}")


def _rename_columns_upgrade() -> None:
    op.alter_column("nft_instances", "nft_id", new_column_name="definition_id")
    op.alter_column("nft_instances", "unique_nft_id", new_column_name="unique_instance_id")

    op.alter_column("bingo_cells", "target_template_id", new_column_name="target_definition_id")
    op.alter_column("bingo_cells", "nft_id", new_column_name="definition_id")
    op.alter_column("bingo_cells", "matched_ownership_id", new_column_name="matched_nft_instance_id")

    op.alter_column("bingo_card_issue_tasks", "center_nft_id", new_column_name="center_definition_id")
    op.alter_column("bingo_card_issue_tasks", "ownership_id", new_column_name="nft_instance_id")
    op.alter_column("bingo_card_issue_tasks", "unique_nft_ref", new_column_name="unique_instance_ref")

    op.alter_column("bingo_period_rewards", "reward_nft_id", new_column_name="reward_definition_id")

    op.alter_column("pre_generated_bingo_cards", "center_nft_id", new_column_name="center_definition_id")
    op.alter_column("pre_generated_bingo_cards", "cell_nft_ids", new_column_name="cell_definition_ids")

    op.alter_column("coupon_templates", "default_display_nft_id", new_column_name="default_display_definition_id")

    op.alter_column("nft_coupon_bindings", "nft_id", new_column_name="definition_id")

    op.alter_column("coupon_instances", "nft_id", new_column_name="definition_id")
    op.alter_column("coupon_instances", "display_nft_id", new_column_name="display_definition_id")
    op.alter_column("coupon_instances", "ownership_id", new_column_name="nft_instance_id")

    op.alter_column("coupon_stores", "nft_id", new_column_name="definition_id")

    op.alter_column("nft_claim_requests", "nft_id", new_column_name="definition_id")
    op.alter_column("nft_claim_requests", "ownership_id", new_column_name="nft_instance_id")

    op.alter_column("prize_draw_results", "nft_id", new_column_name="definition_id")
    op.alter_column("prize_draw_results", "ownership_id", new_column_name="nft_instance_id")

    op.alter_column("raffle_entries", "ownership_id", new_column_name="nft_instance_id")

    op.alter_column("nft_conditions", "required_nft_id", new_column_name="required_definition_id")
    op.alter_column("nft_conditions", "prohibited_nft_id", new_column_name="prohibited_definition_id")

    op.alter_column("nft_templates", "required_nft_id", new_column_name="required_definition_id")
    op.alter_column("nft_templates", "prohibited_nft_id", new_column_name="prohibited_definition_id")


def _rename_columns_downgrade() -> None:
    op.alter_column("nft_templates", "prohibited_definition_id", new_column_name="prohibited_nft_id")
    op.alter_column("nft_templates", "required_definition_id", new_column_name="required_nft_id")

    op.alter_column("nft_conditions", "prohibited_definition_id", new_column_name="prohibited_nft_id")
    op.alter_column("nft_conditions", "required_definition_id", new_column_name="required_nft_id")

    op.alter_column("raffle_entries", "nft_instance_id", new_column_name="ownership_id")

    op.alter_column("prize_draw_results", "nft_instance_id", new_column_name="ownership_id")
    op.alter_column("prize_draw_results", "definition_id", new_column_name="nft_id")

    op.alter_column("nft_claim_requests", "nft_instance_id", new_column_name="ownership_id")
    op.alter_column("nft_claim_requests", "definition_id", new_column_name="nft_id")

    op.alter_column("coupon_stores", "definition_id", new_column_name="nft_id")

    op.alter_column("coupon_instances", "nft_instance_id", new_column_name="ownership_id")
    op.alter_column("coupon_instances", "display_definition_id", new_column_name="display_nft_id")
    op.alter_column("coupon_instances", "definition_id", new_column_name="nft_id")

    op.alter_column("nft_coupon_bindings", "definition_id", new_column_name="nft_id")

    op.alter_column("coupon_templates", "default_display_definition_id", new_column_name="default_display_nft_id")

    op.alter_column("pre_generated_bingo_cards", "cell_definition_ids", new_column_name="cell_nft_ids")
    op.alter_column("pre_generated_bingo_cards", "center_definition_id", new_column_name="center_nft_id")

    op.alter_column("bingo_period_rewards", "reward_definition_id", new_column_name="reward_nft_id")

    op.alter_column("bingo_card_issue_tasks", "unique_instance_ref", new_column_name="unique_nft_ref")
    op.alter_column("bingo_card_issue_tasks", "nft_instance_id", new_column_name="ownership_id")
    op.alter_column("bingo_card_issue_tasks", "center_definition_id", new_column_name="center_nft_id")

    op.alter_column("bingo_cells", "matched_nft_instance_id", new_column_name="matched_ownership_id")
    op.alter_column("bingo_cells", "definition_id", new_column_name="nft_id")
    op.alter_column("bingo_cells", "target_definition_id", new_column_name="target_template_id")

    op.alter_column("nft_instances", "unique_instance_id", new_column_name="unique_nft_id")
    op.alter_column("nft_instances", "definition_id", new_column_name="nft_id")


def _rename_constraints_upgrade() -> None:
    # nft_definitions (formerly nfts)
    _rename_constraint_if_exists(
        "nft_definitions",
        "fk_nfts_bingo_period_id_bingo_periods",
        "fk_nft_definitions_bingo_period_id_bingo_periods",
    )
    _rename_constraint_if_exists(
        "nft_definitions", "nfts_condition_id_fkey", "nft_definitions_condition_id_fkey"
    )
    _rename_constraint_if_exists(
        "nft_definitions",
        "nfts_created_by_admin_id_fkey",
        "nft_definitions_created_by_admin_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_definitions", "nfts_template_id_fkey", "nft_definitions_template_id_fkey"
    )

    # nft_instances (formerly user_nft_ownership)
    _rename_constraint_if_exists(
        "nft_instances",
        "user_nft_ownership_nft_id_fkey",
        "nft_instances_definition_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_instances",
        "user_nft_ownership_user_id_fkey",
        "nft_instances_user_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_instances",
        "user_nft_ownership_bingo_period_id_fkey",
        "nft_instances_bingo_period_id_fkey",
    )

    # dependent tables with renamed columns
    _rename_constraint_if_exists(
        "bingo_cells",
        "bingo_cells_target_template_id_fkey",
        "bingo_cells_target_definition_id_fkey",
    )
    _rename_constraint_if_exists(
        "bingo_cells", "bingo_cells_nft_id_fkey", "bingo_cells_definition_id_fkey"
    )
    _rename_constraint_if_exists(
        "bingo_cells",
        "bingo_cells_matched_ownership_id_fkey",
        "bingo_cells_matched_nft_instance_id_fkey",
    )

    _rename_constraint_if_exists(
        "bingo_card_issue_tasks",
        "bingo_card_issue_tasks_center_nft_id_fkey",
        "bingo_card_issue_tasks_center_definition_id_fkey",
    )
    _rename_constraint_if_exists(
        "bingo_card_issue_tasks",
        "bingo_card_issue_tasks_ownership_id_fkey",
        "bingo_card_issue_tasks_nft_instance_id_fkey",
    )

    _rename_constraint_if_exists(
        "bingo_period_rewards",
        "bingo_period_rewards_reward_nft_id_fkey",
        "bingo_period_rewards_reward_definition_id_fkey",
    )

    _rename_constraint_if_exists(
        "pre_generated_bingo_cards",
        "pre_generated_bingo_cards_center_nft_id_fkey",
        "pre_generated_bingo_cards_center_definition_id_fkey",
    )

    _rename_constraint_if_exists(
        "coupon_templates",
        "coupon_templates_default_display_nft_id_fkey",
        "coupon_templates_default_display_definition_id_fkey",
    )

    _rename_constraint_if_exists(
        "nft_coupon_bindings",
        "nft_coupon_bindings_nft_id_fkey",
        "nft_coupon_bindings_definition_id_fkey",
    )

    _rename_constraint_if_exists(
        "coupon_instances",
        "coupon_instances_nft_id_fkey",
        "coupon_instances_definition_id_fkey",
    )
    _rename_constraint_if_exists(
        "coupon_instances",
        "coupon_instances_display_nft_id_fkey",
        "coupon_instances_display_definition_id_fkey",
    )
    _rename_constraint_if_exists(
        "coupon_instances",
        "coupon_instances_ownership_id_fkey",
        "coupon_instances_nft_instance_id_fkey",
    )

    _rename_constraint_if_exists(
        "coupon_stores", "coupon_stores_nft_id_fkey", "coupon_stores_definition_id_fkey"
    )

    _rename_constraint_if_exists(
        "nft_claim_requests",
        "nft_claim_requests_nft_id_fkey",
        "nft_claim_requests_definition_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_claim_requests",
        "nft_claim_requests_ownership_id_fkey",
        "nft_claim_requests_nft_instance_id_fkey",
    )

    _rename_constraint_if_exists(
        "prize_draw_results",
        "prize_draw_results_nft_id_fkey",
        "prize_draw_results_definition_id_fkey",
    )
    _rename_constraint_if_exists(
        "prize_draw_results",
        "prize_draw_results_ownership_id_fkey",
        "prize_draw_results_nft_instance_id_fkey",
    )

    _rename_constraint_if_exists(
        "raffle_entries",
        "raffle_entries_ownership_id_fkey",
        "raffle_entries_nft_instance_id_fkey",
    )

    _rename_constraint_if_exists(
        "bingo_card_issue_tasks",
        "bingo_card_issue_tasks_ownership_id_key",
        "bingo_card_issue_tasks_nft_instance_id_key",
    )


def _rename_constraints_downgrade() -> None:
    _rename_constraint_if_exists(
        "bingo_card_issue_tasks",
        "bingo_card_issue_tasks_nft_instance_id_key",
        "bingo_card_issue_tasks_ownership_id_key",
    )

    _rename_constraint_if_exists(
        "raffle_entries",
        "raffle_entries_nft_instance_id_fkey",
        "raffle_entries_ownership_id_fkey",
    )

    _rename_constraint_if_exists(
        "prize_draw_results",
        "prize_draw_results_nft_instance_id_fkey",
        "prize_draw_results_ownership_id_fkey",
    )
    _rename_constraint_if_exists(
        "prize_draw_results",
        "prize_draw_results_definition_id_fkey",
        "prize_draw_results_nft_id_fkey",
    )

    _rename_constraint_if_exists(
        "nft_claim_requests",
        "nft_claim_requests_nft_instance_id_fkey",
        "nft_claim_requests_ownership_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_claim_requests",
        "nft_claim_requests_definition_id_fkey",
        "nft_claim_requests_nft_id_fkey",
    )

    _rename_constraint_if_exists(
        "coupon_stores", "coupon_stores_definition_id_fkey", "coupon_stores_nft_id_fkey"
    )

    _rename_constraint_if_exists(
        "coupon_instances",
        "coupon_instances_nft_instance_id_fkey",
        "coupon_instances_ownership_id_fkey",
    )
    _rename_constraint_if_exists(
        "coupon_instances",
        "coupon_instances_display_definition_id_fkey",
        "coupon_instances_display_nft_id_fkey",
    )
    _rename_constraint_if_exists(
        "coupon_instances",
        "coupon_instances_definition_id_fkey",
        "coupon_instances_nft_id_fkey",
    )

    _rename_constraint_if_exists(
        "nft_coupon_bindings",
        "nft_coupon_bindings_definition_id_fkey",
        "nft_coupon_bindings_nft_id_fkey",
    )

    _rename_constraint_if_exists(
        "coupon_templates",
        "coupon_templates_default_display_definition_id_fkey",
        "coupon_templates_default_display_nft_id_fkey",
    )

    _rename_constraint_if_exists(
        "pre_generated_bingo_cards",
        "pre_generated_bingo_cards_center_definition_id_fkey",
        "pre_generated_bingo_cards_center_nft_id_fkey",
    )

    _rename_constraint_if_exists(
        "bingo_period_rewards",
        "bingo_period_rewards_reward_definition_id_fkey",
        "bingo_period_rewards_reward_nft_id_fkey",
    )

    _rename_constraint_if_exists(
        "bingo_card_issue_tasks",
        "bingo_card_issue_tasks_nft_instance_id_fkey",
        "bingo_card_issue_tasks_ownership_id_fkey",
    )
    _rename_constraint_if_exists(
        "bingo_card_issue_tasks",
        "bingo_card_issue_tasks_center_definition_id_fkey",
        "bingo_card_issue_tasks_center_nft_id_fkey",
    )

    _rename_constraint_if_exists(
        "bingo_cells",
        "bingo_cells_matched_nft_instance_id_fkey",
        "bingo_cells_matched_ownership_id_fkey",
    )
    _rename_constraint_if_exists(
        "bingo_cells", "bingo_cells_definition_id_fkey", "bingo_cells_nft_id_fkey"
    )
    _rename_constraint_if_exists(
        "bingo_cells",
        "bingo_cells_target_definition_id_fkey",
        "bingo_cells_target_template_id_fkey",
    )

    _rename_constraint_if_exists(
        "nft_instances",
        "nft_instances_bingo_period_id_fkey",
        "user_nft_ownership_bingo_period_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_instances", "nft_instances_user_id_fkey", "user_nft_ownership_user_id_fkey"
    )
    _rename_constraint_if_exists(
        "nft_instances", "nft_instances_definition_id_fkey", "user_nft_ownership_nft_id_fkey"
    )

    _rename_constraint_if_exists(
        "nft_definitions",
        "nft_definitions_template_id_fkey",
        "nfts_template_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_definitions",
        "nft_definitions_created_by_admin_id_fkey",
        "nfts_created_by_admin_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_definitions",
        "nft_definitions_condition_id_fkey",
        "nfts_condition_id_fkey",
    )
    _rename_constraint_if_exists(
        "nft_definitions",
        "fk_nft_definitions_bingo_period_id_bingo_periods",
        "fk_nfts_bingo_period_id_bingo_periods",
    )


def _rename_indexes_upgrade() -> None:
    _rename_index_if_exists("ix_nfts_id", "ix_nft_definitions_id")
    _rename_index_if_exists("ix_nfts_template_id", "ix_nft_definitions_template_id")
    _rename_index_if_exists("ix_nfts_bingo_period_id", "ix_nft_definitions_bingo_period_id")

    _rename_index_if_exists("ix_user_nft_ownership_id", "ix_nft_instances_id")
    _rename_index_if_exists(
        "ix_user_nft_ownership_bingo_period_id", "ix_nft_instances_bingo_period_id"
    )

    _rename_index_if_exists(
        "ix_bingo_cells_target_template_id", "ix_bingo_cells_target_definition_id"
    )
    _rename_index_if_exists("ix_bingo_cells_nft_id", "ix_bingo_cells_definition_id")

    _rename_index_if_exists(
        "ix_bingo_card_issue_tasks_center_nft_id",
        "ix_bingo_card_issue_tasks_center_definition_id",
    )

    _rename_index_if_exists(
        "ix_bingo_period_rewards_reward_nft_id",
        "ix_bingo_period_rewards_reward_definition_id",
    )

    _rename_index_if_exists(
        "ix_coupon_templates_default_display_nft_id",
        "ix_coupon_templates_default_display_definition_id",
    )

    _rename_index_if_exists("ix_coupon_stores_nft_id", "ix_coupon_stores_definition_id")

    _rename_index_if_exists("ix_nft_claim_requests_nft_id", "ix_nft_claim_requests_definition_id")

    _rename_index_if_exists(
        "ix_coupon_instances_display_nft_id",
        "ix_coupon_instances_display_definition_id",
    )

    _rename_index_if_exists(
        "ix_prize_draw_results_nft_id",
        "ix_prize_draw_results_definition_id",
    )


def _rename_indexes_downgrade() -> None:
    _rename_index_if_exists("ix_prize_draw_results_definition_id", "ix_prize_draw_results_nft_id")

    _rename_index_if_exists(
        "ix_coupon_instances_display_definition_id",
        "ix_coupon_instances_display_nft_id",
    )

    _rename_index_if_exists("ix_nft_claim_requests_definition_id", "ix_nft_claim_requests_nft_id")

    _rename_index_if_exists("ix_coupon_stores_definition_id", "ix_coupon_stores_nft_id")

    _rename_index_if_exists(
        "ix_coupon_templates_default_display_definition_id",
        "ix_coupon_templates_default_display_nft_id",
    )

    _rename_index_if_exists(
        "ix_bingo_period_rewards_reward_definition_id",
        "ix_bingo_period_rewards_reward_nft_id",
    )

    _rename_index_if_exists(
        "ix_bingo_card_issue_tasks_center_definition_id",
        "ix_bingo_card_issue_tasks_center_nft_id",
    )

    _rename_index_if_exists("ix_bingo_cells_definition_id", "ix_bingo_cells_nft_id")
    _rename_index_if_exists(
        "ix_bingo_cells_target_definition_id", "ix_bingo_cells_target_template_id"
    )

    _rename_index_if_exists("ix_nft_instances_bingo_period_id", "ix_user_nft_ownership_bingo_period_id")
    _rename_index_if_exists("ix_nft_instances_id", "ix_user_nft_ownership_id")

    _rename_index_if_exists("ix_nft_definitions_bingo_period_id", "ix_nfts_bingo_period_id")
    _rename_index_if_exists("ix_nft_definitions_template_id", "ix_nfts_template_id")
    _rename_index_if_exists("ix_nft_definitions_id", "ix_nfts_id")


def upgrade() -> None:
    # 3a. Drop old unique constraints
    _drop_constraint_if_exists("prize_draw_results", "uq_prize_draw_result_unique", "unique")
    _drop_constraint_if_exists("user_nft_ownership", "uq_user_nft_once", "unique")

    # 3b. Rename tables
    op.rename_table("nfts", "nft_definitions")
    op.rename_table("user_nft_ownership", "nft_instances")

    # 3c. Rename columns
    _rename_columns_upgrade()

    # 3d + 3f. Rename FK/unique constraints
    _rename_constraints_upgrade()

    # 3e. Rename indexes
    _rename_indexes_upgrade()


def downgrade() -> None:
    # Reverse index and constraint names while table names are still new
    _rename_indexes_downgrade()
    _rename_constraints_downgrade()

    # Reverse column/table renames
    _rename_columns_downgrade()
    op.rename_table("nft_definitions", "nfts")
    op.rename_table("nft_instances", "user_nft_ownership")

    # Restore legacy unique constraints dropped by upgrade
    op.create_unique_constraint(
        "uq_user_nft_once",
        "user_nft_ownership",
        ["user_id", "nft_id"],
    )
    op.create_unique_constraint(
        "uq_prize_draw_result_unique",
        "prize_draw_results",
        ["nft_id", "draw_type_id"],
    )
