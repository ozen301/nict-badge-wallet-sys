from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nictbw.models import (
    Admin,
    Base,
    NFTTemplate,
    PrizeDrawOutcome,
    PrizeDrawType,
    User,
)
from nictbw.workflows import evaluate_draws, run_prize_draw, submit_winning_number


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
                metadata={"source": "game"},
                effective_at=datetime.now(timezone.utc),
            )

            first_result = run_prize_draw(
                session, nft, draw_type, winning_number, threshold=1.0
            )
            self.assertEqual(first_result.outcome, PrizeDrawOutcome.LOSE)
            self.assertEqual(first_result.distance_score, 3.0)
            self.assertEqual(first_result.threshold_used, 1.0)
            result_id = first_result.id

            second_result = run_prize_draw(
                session,
                nft,
                draw_type,
                winning_number,
                threshold=5.0,
                payload={"rerun": True},
            )
            self.assertEqual(second_result.id, result_id)
            self.assertEqual(second_result.outcome, PrizeDrawOutcome.WIN)
            self.assertEqual(second_result.threshold_used, 5.0)
            self.assertEqual(second_result.distance_score, 3.0)
            self.assertEqual(second_result.user_id, user.id)
            self.assertIsNotNone(second_result.ownership_id)
            self.assertEqual(json.loads(second_result.notes)["rerun"], True)
            self.assertIn("source", json.loads(winning_number.metadata_json))

    def test_evaluate_draws_uses_latest_winning_number(self) -> None:
        with self.Session.begin() as session:
            user, template = self._seed_user_and_template(session)
            nft_one = self._mint_nft(session, template, user, origin="abc")
            nft_two = self._mint_nft(session, template, user, origin="abz")

            draw_type = PrizeDrawType(
                internal_name="batch",
                algorithm_key="hamming",
                default_threshold=10.0,
            )
            session.add(draw_type)
            session.flush()

            submit_winning_number(
                session,
                draw_type,
                value="aaa",
                effective_at=datetime.now(timezone.utc) - timedelta(days=1),
            )
            latest = submit_winning_number(
                session,
                draw_type,
                value="abz",
                effective_at=datetime.now(timezone.utc),
            )

            results = evaluate_draws(
                session,
                draw_type,
                nft_ids=[nft_one.id, nft_two.id],
            )

            self.assertEqual(len(results), 2)
            for res in results:
                self.assertEqual(res.winning_number_id, latest.id)
                self.assertIn(res.draw_number, {"abc", "abz"})

    def test_evaluate_draws_empty_ids_returns_empty(self) -> None:
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

            results = evaluate_draws(session, draw_type, nft_ids=[])
            self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()
