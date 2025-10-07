from __future__ import annotations

import unittest
from typing import cast

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nictbw.models import Admin, Base, NFTTemplate, PrizeDrawType, User
from nictbw.workflows import (
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

    def _seed_user_and_template(self, session):
        admin = Admin(paymail="admin@example.com", password_hash="x")
        user = User(in_app_id="draw-user", paymail="wallet@example.com")
        session.add_all([admin, user])
        session.flush()

        template = NFTTemplate(
            prefix="DRW",
            name="Draw Template",
            category="event",
            subcategory="game",
            created_by_admin_id=admin.id,
            minted_count=0,
        )
        session.add(template)
        session.flush()
        return user, template

    def _mint_nft(self, session, template: NFTTemplate, user: User, *, origin: str):
        nft = template.instantiate_nft(shared_key=f"key-{origin}")
        nft.origin = origin
        session.add(nft)
        session.flush()
        nft.issue_dbwise_to(session, user)
        return nft

    def test_run_prize_draw_overwrites_result(self) -> None:
        with self.Session.begin() as session:
            user, template = self._seed_user_and_template(session)
            nft = self._mint_nft(session, template, user, origin="ABC")

            draw_type = PrizeDrawType(
                internal_name="instant",
                algorithm_key="hamming",
                default_threshold=1.0,
            )
            session.add(draw_type)
            session.flush()

            winning_number = submit_winning_number(
                session,
                draw_type,
                value="abd",
            )

            first_result = run_prize_draw(
                session, nft, draw_type, winning_number, threshold=1.0
            )
            self.assertEqual(first_result.outcome, "lose")
            self.assertIsNotNone(first_result.similarity_score)
            self.assertAlmostEqual(cast(float, first_result.similarity_score), 0.875)
            self.assertEqual(first_result.threshold_used, 1.0)
            result_id = first_result.id

            second_result = run_prize_draw(
                session,
                nft,
                draw_type,
                winning_number,
                threshold=0.5,
            )
            self.assertEqual(second_result.id, result_id)
            self.assertEqual(second_result.outcome, "win")
            self.assertEqual(second_result.threshold_used, 0.5)
            self.assertIsNotNone(second_result.similarity_score)
            self.assertAlmostEqual(cast(float, second_result.similarity_score), 0.875)
            self.assertEqual(second_result.user_id, user.id)
            self.assertIsNotNone(second_result.ownership_id)

    def test_run_prize_draw_batch_uses_latest_winning_number(self) -> None:
        with self.Session.begin() as session:
            user, template = self._seed_user_and_template(session)
            nft_one = self._mint_nft(session, template, user, origin="abc")
            nft_two = self._mint_nft(session, template, user, origin="abz")

            draw_type = PrizeDrawType(
                internal_name="batch",
                algorithm_key="hamming",
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
                nfts=[nft_one, nft_two],
            )

            self.assertEqual(len(results), 2)
            for res in results:
                self.assertEqual(res.winning_number_id, latest.id)
                self.assertIn(res.draw_number, {"abc", "abz"})

    def test_run_prize_draw_batch_empty_ids_returns_empty(self) -> None:
        with self.Session.begin() as session:
            user, template = self._seed_user_and_template(session)
            draw_type = PrizeDrawType(
                internal_name="empty",
                algorithm_key="hamming",
                default_threshold=1.0,
            )
            session.add(draw_type)
            session.flush()

            submit_winning_number(session, draw_type, value="abc")

            results = run_prize_draw_batch(session, draw_type, nfts=[])
            self.assertEqual(results, [])

    def test_select_top_prize_draw_results_orders_by_similarity(self) -> None:
        with self.Session.begin() as session:
            user, template = self._seed_user_and_template(session)
            draw_type = PrizeDrawType(
                internal_name="closest", algorithm_key="hamming", default_threshold=None
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
                nft = self._mint_nft(session, template, user, origin=origin)
                result = run_prize_draw(
                    session,
                    nft,
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
                winning_number,
                limit=2,
            )

            self.assertEqual(len(top_two), 2)
            self.assertEqual(top_two[0].draw_number, "abd")
            self.assertEqual(top_two[1].draw_number, "abe")
            for entry in top_two:
                self.assertEqual(entry.outcome, "pending")
                self.assertIsNone(entry.threshold_used)
                self.assertIsNotNone(entry.similarity_score)

            non_pending = select_top_prize_draw_results(
                session,
                draw_type,
                winning_number,
                limit=3,
                include_pending=False,
            )
            self.assertEqual(non_pending, [])


if __name__ == "__main__":
    unittest.main()
