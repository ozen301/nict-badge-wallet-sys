import unittest
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nictbw.models import (
    Base,
    User,
    Admin,
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
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.Session() as session:
            admin = Admin(paymail="a@b.com", password_hash="x")
            session.add(admin)
            session.flush()

            n1 = NFT(
                prefix="P",
                shared_key="s1",
                name="NFT1",
                nft_type="badge",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            n2 = NFT(
                prefix="P",
                shared_key="s2",
                name="NFT2",
                nft_type="badge",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            n3 = NFT(
                prefix="Q",
                shared_key="s3",
                name="NFT3",
                nft_type="badge",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add_all([n1, n2, n3])
            session.commit()

            from nictbw.models.nft import NFT as NFTModel

            count_p = NFTModel.count_nfts_by_prefix(session, "P")
            self.assertEqual(count_p, 2)

            first_p = NFTModel.get_by_prefix(session, "P")
            self.assertIsNotNone(first_p)
            # help static type checkers understand `first_p` is not None
            assert first_p is not None
            self.assertEqual(first_p.prefix, "P")

            same_prefix_count = first_p.count_same_prefix_nfts(session)
            self.assertEqual(same_prefix_count, 2)

    def test_user_issue_nft_creates_ownership_and_increments(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        with self.Session() as session:
            admin = Admin(paymail="owner@admin.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft = NFT(
                prefix="ABC",
                shared_key="key",
                name="Token",
                nft_type="badge",
                minted_count=0,
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", wallet="wallet1")
            session.add_all([nft, user])
            session.flush()

            # Pre-condition
            self.assertEqual(nft.minted_count, 0)
            self.assertEqual(len(user.ownerships), 0)

            # Act
            user.issue_nft(session, nft)
            session.commit()

            # Verify minted_count incremented
            self.assertEqual(nft.minted_count, 1)
            # Ownership created and linked
            self.assertEqual(len(user.ownerships), 1)
            ownership: UserNFTOwnership = user.ownerships[0]
            self.assertEqual(ownership.user_id, user.id)
            self.assertEqual(ownership.nft_id, nft.id)
            self.assertEqual(ownership.serial_number, 0)
            self.assertEqual(ownership.unique_nft_id, "ABC-0")
            self.assertEqual(ownership.acquired_at, nft.created_at)

    def test_bingo_completed_lines(self):
        card = BingoCard(user_id=1, issued_at=datetime.now())
        # Prepare 9 cells, initially locked
        for i in range(9):
            cell = BingoCell(
                bingo_card_id=1,
                idx=i,
                target_nft_id=1,
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

