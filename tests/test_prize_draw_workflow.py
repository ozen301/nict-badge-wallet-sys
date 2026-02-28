from __future__ import annotations

import unittest
from datetime import datetime, timezone
from typing import cast

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from nictbw.models import (
    Admin,
    Base,
    BingoCard,
    BingoCell,
    NFTDefinition,
    NFTInstance,
    PrizeDrawResult,
    PrizeDrawType,
    User,
)
from nictbw.workflows import (
    _rank_prize_draw_results_with_ties,
    run_bingo_prize_draw,
    run_final_attendance_prize_draw,
    run_prize_draw,
    run_prize_draw_batch,
    select_top_prize_draw_results,
    submit_winning_number,
)


class PrizeDrawWorkflowTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, future=True, expire_on_commit=False
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def _seed_user_and_admin(self, session):
        admin = Admin(email="admin@example.com", password_hash="x")
        user = User(in_app_id="draw-user", paymail="wallet@example.com")
        session.add_all([admin, user])
        session.flush()
        return user, admin

    def _mint_nft(self, session, admin: Admin, user: User, *, origin: str) -> NFTInstance:
        prefix = f"NFTDefinition-{origin}"
        definition = NFTDefinition(
            prefix=prefix,
            shared_key=f"key-{origin}",
            name=f"NFTDefinition {origin}",
            nft_type="default",
            category="event",
            subcategory="game",
            created_by_admin_id=admin.id,
        )
        session.add(definition)
        session.flush()
        return definition.issue_dbwise_to_user(session, user, nft_origin=origin)

    def test_run_prize_draw_overwrites_result(self) -> None:
        with self.Session.begin() as session:
            user, admin = self._seed_user_and_admin(session)
            instance = self._mint_nft(session, admin, user, origin="ABC")

            draw_type = PrizeDrawType(
                internal_name="instant",
                algorithm_key="sha256_hex_proximity",
                default_threshold=0.8,
            )
            session.add(draw_type)
            session.flush()

            winning_number = submit_winning_number(
                session,
                draw_type,
                value="abd",
            )

            lose_threshold = 0.8
            first_result = run_prize_draw(
                session, instance, draw_type, winning_number, threshold=lose_threshold
            )
            self.assertEqual(first_result.outcome, "lose")
            self.assertIsNotNone(first_result.similarity_score)
            self.assertAlmostEqual(
                cast(float, first_result.similarity_score),
                0.7752364105046057,
            )
            self.assertEqual(first_result.draw_top_digits, "8434236848")
            self.assertEqual(first_result.winning_top_digits, "7471127736")
            self.assertEqual(first_result.threshold_used, lose_threshold)
            result_id = first_result.id

            second_result = run_prize_draw(
                session,
                instance,
                draw_type,
                winning_number,
                threshold=0.7,
            )
            self.assertEqual(second_result.id, result_id)
            self.assertEqual(second_result.outcome, "win")
            self.assertEqual(second_result.threshold_used, 0.7)
            self.assertIsNotNone(second_result.similarity_score)
            self.assertAlmostEqual(
                cast(float, second_result.similarity_score),
                0.7752364105046057,
            )
            self.assertEqual(second_result.draw_top_digits, "8434236848")
            self.assertEqual(second_result.winning_top_digits, "7471127736")
            self.assertEqual(second_result.user_id, user.id)
            self.assertIsNotNone(second_result.nft_instance_id)

    def test_run_prize_draw_batch_uses_latest_winning_number(self) -> None:
        with self.Session.begin() as session:
            user, admin = self._seed_user_and_admin(session)
            instance_one = self._mint_nft(session, admin, user, origin="abc")
            instance_two = self._mint_nft(session, admin, user, origin="abz")

            draw_type = PrizeDrawType(
                internal_name="batch",
                algorithm_key="sha256_hex_proximity",
                default_threshold=0.5,
            )
            session.add(draw_type)
            session.flush()

            submit_winning_number(
                session,
                draw_type,
                value="aaa",
            )
            latest = submit_winning_number(
                session,
                draw_type,
                value="abz",
            )

            results = run_prize_draw_batch(
                session,
                draw_type,
                nft_instances=[instance_one, instance_two],
            )

            self.assertEqual(len(results), 2)
            for res in results:
                self.assertEqual(res.winning_number_id, latest.id)
                self.assertIn(res.draw_number, {"abc", "abz"})

    def test_run_prize_draw_keyword_hard_breaks(self) -> None:
        with self.Session.begin() as session:
            user, admin = self._seed_user_and_admin(session)
            nft_instance = self._mint_nft(session, admin, user, origin="KW")

            draw_type = PrizeDrawType(
                internal_name="keyword-breaks",
                algorithm_key="sha256_hex_proximity",
                default_threshold=0.5,
            )
            session.add(draw_type)
            session.flush()
            winning_number = submit_winning_number(session, draw_type, value="kw")

            with self.assertRaises(TypeError):
                run_prize_draw(
                    session,
                    instance=nft_instance,
                    draw_type=draw_type,
                    winning_number=winning_number,
                )

            with self.assertRaises(TypeError):
                run_prize_draw_batch(
                    session,
                    draw_type=draw_type,
                    instances=[nft_instance],
                    winning_number=winning_number,
                )

    def test_run_prize_draw_batch_empty_ids_returns_empty(self) -> None:
        with self.Session.begin() as session:
            user, _admin = self._seed_user_and_admin(session)
            draw_type = PrizeDrawType(
                internal_name="empty",
                algorithm_key="sha256_hex_proximity",
                default_threshold=1.0,
            )
            session.add(draw_type)
            session.flush()

            submit_winning_number(session, draw_type, value="abc")

            results = run_prize_draw_batch(session, draw_type, nft_instances=[])
            self.assertEqual(results, [])

    def test_run_prize_draw_batch_raises_on_same_definition_instances(self) -> None:
        with self.Session.begin() as session:
            user_one, admin = self._seed_user_and_admin(session)
            user_two = User(in_app_id="draw-user-2", paymail="draw-user-2@wallet")
            session.add(user_two)
            session.flush()

            definition = NFTDefinition(
                prefix="BATCH-CONFLICT",
                shared_key="batch-conflict-key",
                name="Batch Conflict",
                nft_type="default",
                category="event",
                subcategory="game",
                created_by_admin_id=admin.id,
            )
            session.add(definition)
            session.flush()

            instance_one = definition.issue_dbwise_to_user(
                session, user_one, nft_origin="conflict-1"
            )
            instance_two = definition.issue_dbwise_to_user(
                session, user_two, nft_origin="conflict-2"
            )

            draw_type = PrizeDrawType(
                internal_name="batch-conflict",
                algorithm_key="sha256_hex_proximity",
                default_threshold=None,
            )
            session.add(draw_type)
            session.flush()
            submit_winning_number(session, draw_type, value="conflict")

            with self.assertRaises(ValueError):
                run_prize_draw_batch(
                    session,
                    draw_type,
                    nft_instances=[instance_one, instance_two],
                )

    def test_run_prize_draw_raises_on_conflicting_existing_definition_result(self) -> None:
        with self.Session.begin() as session:
            user_one, admin = self._seed_user_and_admin(session)
            user_two = User(in_app_id="draw-user-3", paymail="draw-user-3@wallet")
            session.add(user_two)
            session.flush()

            definition = NFTDefinition(
                prefix="SINGLE-CONFLICT",
                shared_key="single-conflict-key",
                name="Single Conflict",
                nft_type="default",
                category="event",
                subcategory="game",
                created_by_admin_id=admin.id,
            )
            session.add(definition)
            session.flush()

            instance_one = definition.issue_dbwise_to_user(
                session, user_one, nft_origin="single-conflict-1"
            )
            instance_two = definition.issue_dbwise_to_user(
                session, user_two, nft_origin="single-conflict-2"
            )

            draw_type = PrizeDrawType(
                internal_name="single-conflict",
                algorithm_key="sha256_hex_proximity",
                default_threshold=None,
            )
            session.add(draw_type)
            session.flush()
            winning_number = submit_winning_number(session, draw_type, value="single")

            run_prize_draw(
                session,
                instance_one,
                draw_type,
                winning_number=winning_number,
            )

            with self.assertRaises(ValueError):
                run_prize_draw(
                    session,
                    instance_two,
                    draw_type,
                    winning_number=winning_number,
                )

    def test_select_top_prize_draw_results_orders_by_similarity(self) -> None:
        with self.Session.begin() as session:
            user, admin = self._seed_user_and_admin(session)
            draw_type = PrizeDrawType(
                internal_name="closest",
                algorithm_key="sha256_hex_proximity",
                default_threshold=None,
            )
            session.add(draw_type)
            session.flush()

            winning_number = submit_winning_number(
                session,
                draw_type,
                value="abd",
            )

            origins = ["abd", "abe", "abz"]
            for origin in origins:
                instance = self._mint_nft(session, admin, user, origin=origin)
                result = run_prize_draw(
                    session,
                    instance,
                    draw_type,
                    winning_number,
                )
                self.assertIsNone(result.threshold_used)
                self.assertEqual(result.outcome, "pending")
                self.assertIsNotNone(result.similarity_score)

            with self.assertRaises(ValueError):
                select_top_prize_draw_results(
                    session, draw_type, winning_number, limit=0
                )

            top_two = select_top_prize_draw_results(
                session,
                draw_type,
                limit=2,
            )

            self.assertEqual(len(top_two), 2)
            self.assertEqual(top_two[0].draw_number, "abd")
            self.assertEqual(top_two[1].draw_number, "abz")
            for entry in top_two:
                self.assertEqual(entry.outcome, "pending")
                self.assertIsNone(entry.threshold_used)
                self.assertIsNotNone(entry.similarity_score)

            non_pending = select_top_prize_draw_results(
                session,
                draw_type,
                limit=3,
                include_pending=False,
            )
            self.assertEqual(non_pending, [])

    def test_select_top_prize_draw_results_requires_winning_number(self) -> None:
        with self.Session.begin() as session:
            draw_type = PrizeDrawType(
                internal_name="no-winning-number",
                algorithm_key="sha256_hex_proximity",
                default_threshold=0.75,
            )
            session.add(draw_type)
            session.flush()

            with self.assertRaises(ValueError):
                select_top_prize_draw_results(session, draw_type, limit=1)


class PrizeDrawWorkflowSelectionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, future=True, expire_on_commit=False
        )

    def tearDown(self) -> None:
        self.engine.dispose()

    def test_run_bingo_prize_draw_limits_to_completed_lines(self) -> None:
        with self.Session.begin() as session:
            admin = Admin(email="admin@example.com", password_hash="x")
            user = User(in_app_id="bingo-player", paymail="player@example.com")
            session.add_all([admin, user])
            session.flush()

            line_defs = [
                NFTDefinition(
                    prefix=f"LINE{i}",
                    shared_key=f"line-{i}",
                    name=f"Line {i}",
                    nft_type="default",
                    category="game",
                    subcategory=f"cell-{i}",
                    created_by_admin_id=admin.id,
                )
                for i in range(3)
            ]
            filler_def = NFTDefinition(
                prefix="FILL",
                shared_key="filler",
                name="Filler",
                nft_type="default",
                category="game",
                subcategory="filler",
                created_by_admin_id=admin.id,
            )
            session.add_all(line_defs + [filler_def])
            session.flush()

            instances: list[NFTInstance] = []
            for i, definition in enumerate(line_defs):
                instances.append(
                    definition.issue_dbwise_to_user(session, user, nft_origin=f"origin-{i}")
                )

            ownership_by_nft = {o.definition_id: o for o in user.nft_instances}

            card = BingoCard(
                user_id=user.id,
                issued_at=datetime.now(timezone.utc),
                state="active",
            )
            session.add(card)
            session.flush()

            cells: list[BingoCell] = []
            for idx in range(9):
                unlocked = idx in (0, 1, 2)
                definition_id = instances[idx].definition_id if unlocked else None
                nft_instance_id = (
                    ownership_by_nft[definition_id].id
                    if unlocked and definition_id is not None
                    else None
                )
                cells.append(
                    BingoCell(
                        bingo_card_id=card.id,
                        idx=idx,
                        target_definition_id=(
                            line_defs[idx].id if idx < 3 else filler_def.id
                        ),
                        definition_id=definition_id,
                        matched_nft_instance_id=nft_instance_id,
                        state="unlocked" if unlocked else "locked",
                        unlocked_at=datetime.now(timezone.utc) if unlocked else None,
                    )
                )
            card.cells.extend(cells)
            session.flush()

            draw_type = PrizeDrawType(
                internal_name="bingo-draw",
                algorithm_key="sha256_hex_proximity",
                default_threshold=None,
            )
            session.add(draw_type)
            session.flush()
            winning_number = submit_winning_number(
                session,
                draw_type,
                value="origin-0",
            )

            winners = run_bingo_prize_draw(
                session,
                draw_type,
                winning_number=winning_number,
                limit=1,
            )

            all_results = session.scalars(
                select(PrizeDrawResult).where(PrizeDrawResult.draw_type_id == draw_type.id)
            ).all()

            self.assertEqual(len(all_results), 3)
            self.assertEqual(len(winners), 1)
            self.assertIn(winners[0].nft_instance_id, {inst.id for inst in instances[:3]})

    def test_run_final_attendance_prize_draw_filters_by_prefix(self) -> None:
        with self.Session.begin() as session:
            admin = Admin(email="admin2@example.com", password_hash="y")
            user = User(in_app_id="final-player", paymail="final@example.com")
            session.add_all([admin, user])
            session.flush()

            attendance_nft = NFTDefinition(
                prefix="FINAL-DAY",
                shared_key="attendance",
                name="Final Attendance",
                nft_type="default",
                category="event",
                subcategory="final-day",
                created_by_admin_id=admin.id,
            )
            other_nft = NFTDefinition(
                prefix="NON-FINAL",
                shared_key="other",
                name="Other",
                nft_type="default",
                category="event",
                subcategory="other",
                created_by_admin_id=admin.id,
            )
            session.add_all([attendance_nft, other_nft])
            session.flush()

            attendance_instance = attendance_nft.issue_dbwise_to_user(
                session, user, nft_origin="final-origin"
            )
            other_instance = other_nft.issue_dbwise_to_user(
                session, user, nft_origin="other-origin"
            )

            draw_type = PrizeDrawType(
                internal_name="final-attendance",
                algorithm_key="sha256_hex_proximity",
                default_threshold=None,
            )
            session.add(draw_type)
            session.flush()
            winning_number = submit_winning_number(
                session,
                draw_type,
                value="final-origin",
            )

            winners = run_final_attendance_prize_draw(
                session,
                draw_type,
                attendance_definition_id=attendance_nft.id,
                winning_number=winning_number,
                limit=1,
            )

            all_results = session.scalars(
                select(PrizeDrawResult).where(PrizeDrawResult.draw_type_id == draw_type.id)
            ).all()

            self.assertEqual(len(all_results), 1)
            self.assertEqual(len(winners), 1)
            self.assertEqual(winners[0].nft_instance_id, attendance_instance.id)
            self.assertNotEqual(winners[0].nft_instance_id, other_instance.id)

    def test_rank_prize_draw_results_with_ties_includes_cutoff(self) -> None:
        base_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        top = PrizeDrawResult(
            draw_type_id=1,
            winning_number_id=1,
            user_id=1,
            definition_id=1,
            nft_instance_id=1,
            draw_number="top",
            similarity_score=0.9,
            evaluated_at=base_time,
        )
        tie_a = PrizeDrawResult(
            draw_type_id=1,
            winning_number_id=1,
            user_id=1,
            definition_id=2,
            nft_instance_id=1,
            draw_number="tie-a",
            similarity_score=0.8,
            evaluated_at=base_time.replace(hour=1),
        )
        tie_b = PrizeDrawResult(
            draw_type_id=1,
            winning_number_id=1,
            user_id=1,
            definition_id=3,
            nft_instance_id=1,
            draw_number="tie-b",
            similarity_score=0.8,
            evaluated_at=base_time.replace(hour=2),
        )

        winners = _rank_prize_draw_results_with_ties(
            [tie_b, tie_a, top],
            limit=2,
        )

        self.assertEqual(len(winners), 3)
        self.assertEqual([w.definition_id for w in winners], [1, 2, 3])


if __name__ == "__main__":
    unittest.main()
