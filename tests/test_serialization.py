import unittest
from datetime import datetime, timezone
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nictbw.models import Base, Admin, User, NFT, BingoCard, BingoCell


class SerializationTestCase(unittest.TestCase):
    def setUp(self):
        # In-memory SQLite for isolation
        self.engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(
            bind=self.engine, future=True, expire_on_commit=False
        )

    def tearDown(self):
        self.engine.dispose()

    def test_nft_to_json_and_str(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="ser-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft = NFT(
                prefix="SER",
                shared_key="shared",
                name="Serializable",
                nft_type="default",
                category="cat",
                subcategory="sub",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(nft)
            session.flush()

            d = nft.to_json()
            self.assertEqual(d["prefix"], "SER")
            self.assertEqual(d["name"], "Serializable")
            self.assertEqual(d["category"], "cat")
            self.assertEqual(d["subcategory"], "sub")
            self.assertIsNone(d.get("max_supply"))
            self.assertEqual(d["minted_count"], 0)
            self.assertIn("created_at", d)
            self.assertIn("updated_at", d)
            # ISO strings should be present (basic shape check)
            self.assertIsInstance(d["created_at"], str)
            self.assertIsInstance(d["updated_at"], str)

            # NFT serialization uses the dict directly
            parsed = json.loads(json.dumps(d))
            self.assertEqual(parsed, d)

    def test_bingocell_to_json_and_str(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="cell-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft = NFT(
                prefix="CELL",
                shared_key="shared",
                name="CellTpl",
                nft_type="default",
                category="cat",
                subcategory="subc",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            card = BingoCard(user_id=1, issued_at=now)
            session.add_all([nft, user, card])
            session.flush()

            cell = BingoCell(
                bingo_card_id=card.id,
                idx=0,
                target_template_id=nft.id,
                state="locked",
            )
            session.add(cell)
            session.flush()

            d = cell.to_json()
            self.assertEqual(d["idx"], 0)
            self.assertEqual(d["state"], "locked")
            self.assertIsNone(d["unlocked_at"])
            self.assertIsNone(d["nft_id"])
            self.assertIn("target_template", d)
            self.assertIsInstance(d["target_template"], dict)
            self.assertEqual(d["target_template"]["id"], nft.id)
            self.assertEqual(d["target_template"]["prefix"], "CELL")

            s = cell.to_json_str()
            parsed = json.loads(s)
            self.assertEqual(parsed, d)

    def test_bingocard_to_json_and_str(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="card-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            # Create 9 NFT definitions
            definitions = []
            for i in range(9):
                nft = NFT(
                    prefix=f"T{i}",
                    shared_key=f"shared-{i}",
                    name=f"T{i}",
                    nft_type="default",
                    category="cat",
                    subcategory=f"s{i}",
                    created_by_admin_id=admin.id,
                    created_at=now,
                    updated_at=now,
                )
                definitions.append(nft)
            user = User(in_app_id="u1", paymail="wallet1")
            card = BingoCard(user_id=1, issued_at=now)
            session.add_all(definitions + [user, card])
            session.flush()

            # Add 9 cells
            for i, nft in enumerate(definitions):
                cell = BingoCell(
                    bingo_card_id=card.id,
                    idx=i,
                    target_template_id=nft.id,
                    state="locked",
                )
                session.add(cell)
            session.flush()

            d = card.to_json()
            self.assertEqual(d["user_id"], 1)
            self.assertEqual(d["state"], "active")
            self.assertIsInstance(d["issued_at"], str)
            # Should have 9 cells
            self.assertEqual(len(d["cells"]), 9)
            # Ensure each cell has a template embedded
            for i, cell_d in enumerate(d["cells"]):
                self.assertEqual(cell_d["idx"], i)
                self.assertIn("target_template", cell_d)
                self.assertIsInstance(cell_d["target_template"], dict)
                self.assertEqual(cell_d["target_template"]["prefix"], f"T{i}")

            s = card.to_json_str()
            parsed = json.loads(s)
            self.assertEqual(parsed, d)


if __name__ == "__main__":
    unittest.main()
