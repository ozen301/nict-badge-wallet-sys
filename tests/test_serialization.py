import unittest
from datetime import datetime, timezone
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from nictbw.models import (
    Base,
    Admin,
    User,
    NFTTemplate,
    BingoCard,
    BingoCell,
)


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

    def test_nfttemplate_to_json_and_str(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="ser-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            tpl = NFTTemplate(
                prefix="SER",
                name="Serializable",
                category="cat",
                subcategory="sub",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(tpl)
            session.flush()

            d = tpl.to_json()
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

            s = tpl.to_json_str()
            parsed = json.loads(s)
            self.assertEqual(parsed, d)

    def test_bingocell_to_json_and_str(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="cell-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            tpl = NFTTemplate(
                prefix="CELL",
                name="CellTpl",
                category="cat",
                subcategory="subc",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            card = BingoCard(user_id=1, issued_at=now)
            session.add_all([tpl, user, card])
            session.flush()

            cell = BingoCell(
                bingo_card_id=card.id,
                idx=0,
                target_template_id=tpl.id,
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
            self.assertEqual(d["target_template"]["id"], tpl.id)
            self.assertEqual(d["target_template"]["prefix"], "CELL")

            s = cell.to_json_str()
            parsed = json.loads(s)
            self.assertEqual(parsed, d)

    def test_bingocard_to_json_and_str(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="card-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            # Create 9 templates
            templates = []
            for i in range(9):
                tpl = NFTTemplate(
                    prefix=f"T{i}",
                    name=f"T{i}",
                    category="cat",
                    subcategory=f"s{i}",
                    created_by_admin_id=admin.id,
                    created_at=now,
                    updated_at=now,
                )
                templates.append(tpl)
            user = User(in_app_id="u1", paymail="wallet1")
            card = BingoCard(user_id=1, issued_at=now)
            session.add_all(templates + [user, card])
            session.flush()

            # Add 9 cells
            for i, tpl in enumerate(templates):
                cell = BingoCell(
                    bingo_card_id=card.id,
                    idx=i,
                    target_template_id=tpl.id,
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
