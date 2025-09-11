import unittest
from datetime import datetime, timezone

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
        self.Session = sessionmaker(bind=self.engine, future=True, expire_on_commit=False)

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
            user.issue_nft_dbwise(session, nft1)
            nft2 = tpl_p.instantiate_nft(shared_key="s2")
            user.issue_nft_dbwise(session, nft2)
            nft3 = tpl_q.instantiate_nft(shared_key="s3")
            user.issue_nft_dbwise(session, nft3)
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
            user.issue_nft_dbwise(session, nft)
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
            user.issue_nft_dbwise(session, nft1)

            with self.assertRaises(ValueError):
                template.instantiate_nft(shared_key="s2")

            nft2 = NFT(
                template_id=template.id,
                shared_key="s3",
                created_by_admin_id=admin.id,
            )
            with self.assertRaises(ValueError):
                user.issue_nft_dbwise(session, nft2)

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


if __name__ == "__main__":
    unittest.main()

