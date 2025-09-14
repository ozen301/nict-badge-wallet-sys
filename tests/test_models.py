import unittest
from datetime import datetime, timezone
import random

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nictbw.models import (
    Base,
    User,
    Admin,
    NFTTemplate,
    NFT,
    UserNFTOwnership,
    BingoCard,
    BingoCell,
)


class DBTestCase(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite for isolation
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, future=True, expire_on_commit=False
        )

    def tearDown(self):
        self.engine.dispose()

    def test_admin_get_by_paymail(self):
        with self.Session() as session:
            admin = Admin(paymail="admin@example.com", password_hash="x")
            session.add(admin)
            session.commit()

            found = Admin.get_by_paymail(session, "admin@example.com")
            self.assertIsNotNone(found)
            # help static type checkers understand `found` is not None
            assert found is not None
            self.assertEqual(found.paymail, "admin@example.com")

    def test_nft_count_and_get_by_prefix(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="a@b.com", password_hash="x")
            session.add(admin)
            session.flush()

            tpl_p = NFTTemplate(
                prefix="P",
                name="TemplateP",
                category="cat",
                subcategory="subp",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            tpl_q = NFTTemplate(
                prefix="Q",
                name="TemplateQ",
                category="cat",
                subcategory="subq",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([tpl_p, tpl_q, user])
            session.flush()

            nft1 = tpl_p.instantiate_nft(shared_key="s1")
            nft1.issue_dbwise_to(session, user)
            nft2 = tpl_p.instantiate_nft(shared_key="s2")
            nft2.issue_dbwise_to(session, user)
            nft3 = tpl_q.instantiate_nft(shared_key="s3")
            nft3.issue_dbwise_to(session, user)
            session.commit()

            count_p = NFT.count_nfts_by_prefix(session, "P")
            self.assertEqual(count_p, 2)

            first_p = NFTTemplate.get_by_prefix(session, "P")
            self.assertIsNotNone(first_p)
            assert first_p is not None
            self.assertEqual(first_p.prefix, "P")
            self.assertEqual(first_p.minted_count, 2)

    def test_user_issue_nft_creates_ownership_and_increments(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="owner@admin.com", password_hash="x")
            session.add(admin)
            session.flush()

            template = NFTTemplate(
                prefix="ABC",
                name="Token",
                category="cat",
                subcategory="sub",
                minted_count=0,
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([template, user])
            session.flush()

            # Pre-condition
            self.assertEqual(template.minted_count, 0)
            self.assertEqual(len(user.ownerships), 0)

            # Act
            nft = template.instantiate_nft(shared_key="key")
            nft.issue_dbwise_to(session, user)
            session.commit()

            # Verify minted_count incremented
            self.assertEqual(template.minted_count, 1)
            # Ownership created and linked
            self.assertEqual(len(user.ownerships), 1)
            ownership: UserNFTOwnership = user.ownerships[0]
            self.assertEqual(ownership.user_id, user.id)
            self.assertEqual(ownership.nft_id, nft.id)
            self.assertEqual(ownership.serial_number, 0)
            self.assertEqual(ownership.unique_nft_id, "ABC_key")
            self.assertEqual(ownership.acquired_at, nft.created_at)

    def test_template_max_supply_enforced(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="admin@max.com", password_hash="x")
            session.add(admin)
            session.flush()

            template = NFTTemplate(
                prefix="SUP",
                name="Token",
                category="cat",
                subcategory="sub",
                max_supply=1,
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([template, user])
            session.flush()

            nft1 = template.instantiate_nft(shared_key="s1")
            nft1.issue_dbwise_to(session, user)

            with self.assertRaises(ValueError):
                template.instantiate_nft(shared_key="s2")

            nft2 = NFT(
                template_id=template.id,
                shared_key="s3",
                created_by_admin_id=admin.id,
            )
            with self.assertRaises(ValueError):
                nft2.issue_dbwise_to(session, user)

    def test_bingo_completed_lines(self):
        card = BingoCard(user_id=1, issued_at=datetime.now(timezone.utc))
        # Prepare 9 cells, initially locked
        for i in range(9):
            cell = BingoCell(
                bingo_card_id=1,
                idx=i,
                target_template_id=1,
                state="locked",
            )
            card.cells.append(cell)

        # Unlock first row
        card.cells[0].state = "unlocked"
        card.cells[1].state = "unlocked"
        card.cells[2].state = "unlocked"

        # Unlock a diagonal as well
        card.cells[4].state = "unlocked"
        card.cells[8].state = "unlocked"

        lines = card.completed_lines
        self.assertIn((0, 1, 2), lines)
        self.assertIn((0, 4, 8), lines)
        # Ensure no false positives: a column not fully unlocked
        self.assertNotIn((0, 3, 6), lines)

    def test_issue_nft_unlocks_bingo_cells_and_completes_card(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            tpl_a = NFTTemplate(
                prefix="A",
                name="A",
                category="cat",
                subcategory="sa",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            tpl_b = NFTTemplate(
                prefix="B",
                name="B",
                category="cat",
                subcategory="sb",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            tpl_c = NFTTemplate(
                prefix="C",
                name="C",
                category="cat",
                subcategory="sc",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            tpl_x = NFTTemplate(
                prefix="X",
                name="X",
                category="cat",
                subcategory="sx",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([tpl_a, tpl_b, tpl_c, tpl_x, user])
            session.flush()

            card = BingoCard(user_id=user.id, issued_at=now)
            session.add(card)
            session.flush()

            cells = [
                BingoCell(bingo_card_id=card.id, idx=0, target_template_id=tpl_a.id),
                BingoCell(bingo_card_id=card.id, idx=1, target_template_id=tpl_b.id),
                BingoCell(bingo_card_id=card.id, idx=2, target_template_id=tpl_c.id),
            ]
            for i in range(3, 9):
                cells.append(
                    BingoCell(bingo_card_id=card.id, idx=i, target_template_id=tpl_x.id)
                )
            for c in cells:
                card.cells.append(c)
                session.add(c)
            session.flush()

            nft_a = tpl_a.instantiate_nft(shared_key="sa")
            nft_a.issue_dbwise_to(session, user)
            nft_b = tpl_b.instantiate_nft(shared_key="sb")
            nft_b.issue_dbwise_to(session, user)
            nft_c = tpl_c.instantiate_nft(shared_key="sc")
            nft_c.issue_dbwise_to(session, user)
            session.commit()

            # Only a row unlocked so far; card should still be active
            self.assertEqual(card.state, "active")
            self.assertIsNone(card.completed_at)

            # Unlock remaining cells with template X NFTs
            for i in range(6):
                nft_x = tpl_x.instantiate_nft(shared_key=f"sx{i}")
                nft_x.issue_dbwise_to(session, user)
            session.commit()

            self.assertEqual(card.state, "completed")
            self.assertIsNotNone(card.completed_at)
            self.assertTrue(all(c.state == "unlocked" for c in card.cells))
            self.assertTrue(all(c.matched_ownership_id is not None for c in card.cells))

    def test_user_unlock_cells_for_nft(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            tpl = NFTTemplate(
                prefix="T",
                name="TokenT",
                category="cat",
                subcategory="subt",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            tpl_other = NFTTemplate(
                prefix="O",
                name="Other",
                category="cat",
                subcategory="subo",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([tpl, tpl_other, user])
            session.flush()

            nft = tpl.instantiate_nft(shared_key="s1")
            nft.issue_dbwise_to(session, user)

            card = BingoCard(user_id=user.id, issued_at=now)
            session.add(card)
            session.flush()

            cells = [BingoCell(bingo_card_id=card.id, idx=0, target_template_id=tpl.id)]
            for i in range(1, 9):
                cells.append(
                    BingoCell(
                        bingo_card_id=card.id,
                        idx=i,
                        target_template_id=tpl_other.id,
                    )
                )
            for c in cells:
                card.cells.append(c)
                session.add(c)
            session.flush()

            cell = cells[0]
            self.assertEqual(cell.state, "locked")

            result = user.unlock_cells_for_nft(session, nft)
            self.assertTrue(result)
            self.assertEqual(cell.state, "unlocked")
            self.assertEqual(cell.matched_ownership_id, user.ownerships[0].id)

            # Reset and test using the NFT's ID
            cell.state = "locked"
            cell.nft_id = None
            cell.matched_ownership_id = None
            session.flush()

            result = user.unlock_cells_for_nft(session, nft.id)
            self.assertTrue(result)
            self.assertEqual(cell.state, "unlocked")
            self.assertEqual(cell.matched_ownership_id, user.ownerships[0].id)

    def test_bingocard_generate_for_user(self):
        now = datetime.now(timezone.utc)
        rng = random.Random(0)
        with self.Session() as session:
            admin = Admin(paymail="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            templates = [
                NFTTemplate(
                    prefix=f"T{i}",
                    name=f"T{i}",
                    category="cat",
                    subcategory=f"s{i}",
                    created_by_admin_id=admin.id,
                    created_at=now,
                    updated_at=now,
                    triggers_bingo_card=(i == 0),
                )
                for i in range(10)
            ]
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all(templates + [user])
            session.flush()

            nft = templates[0].instantiate_nft(shared_key="s1")
            nft.issue_dbwise_to(session, user)
            session.commit()

            card = BingoCard.generate_for_user(
                session=session,
                user=user,
                center_template=templates[0],
                rng=rng,
            )
            self.assertEqual(len(card.cells), 9)
            self.assertEqual(
                len({c.target_template_id for c in card.cells}), 9
            )
            center = next(c for c in card.cells if c.idx == 4)
            self.assertEqual(center.state, "unlocked")

    def test_user_ensure_bingo_cards(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            tpl_trigger = NFTTemplate(
                prefix="TR",
                name="Trigger",
                category="cat",
                subcategory="subtr",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
                triggers_bingo_card=True,
            )
            others = [
                NFTTemplate(
                    prefix=f"O{i}",
                    name=f"O{i}",
                    category="cat",
                    subcategory=f"so{i}",
                    created_by_admin_id=admin.id,
                    created_at=now,
                    updated_at=now,
                )
                for i in range(8)
            ]
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([tpl_trigger, user] + others)
            session.flush()

            nft = tpl_trigger.instantiate_nft(shared_key="s1")
            nft.issue_dbwise_to(session, user)
            session.commit()

            created = user.ensure_bingo_cards(session)
            session.commit()
            self.assertEqual(created, 1)
            self.assertEqual(len(user.bingo_cards), 1)

    def test_ownership_get_by_user_and_nft(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            tpl = NFTTemplate(
                prefix="T",
                name="TokenT",
                category="cat",
                subcategory="subt",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([tpl, user])
            session.flush()

            nft = tpl.instantiate_nft(shared_key="s1")
            nft.issue_dbwise_to(session, user)
            session.commit()

            ownership = UserNFTOwnership.get_by_user_and_nft(session, user, nft)
            self.assertIsNotNone(ownership)
            assert ownership is not None
            self.assertEqual(ownership.user_id, user.id)
            self.assertEqual(ownership.nft_id, nft.id)

            # Also verify lookup works with IDs
            ownership2 = UserNFTOwnership.get_by_user_and_nft(
                session, user.id, nft.id
            )
            self.assertIsNotNone(ownership2)
            assert ownership2 is not None
            self.assertEqual(ownership2.id, ownership.id)


if __name__ == "__main__":
    unittest.main()
