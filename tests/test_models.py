import json
import random
import unittest
import warnings
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from sqlalchemy.exc import IntegrityError
from unittest.mock import patch

if TYPE_CHECKING:
    from nictbw.blockchain.api import ChainClient
else:
    ChainClient = object

from nictbw.models import (
    Base,
    User,
    Admin,
    NFTTemplate,
    NFT,
    UserNFTOwnership,
    BingoCard,
    BingoCell,
    PrizeDrawType,
    PrizeDrawWinningNumber,
    PrizeDrawResult,
)


class DummyChainClient:
    def __init__(self, items: list[dict]):
        self._items = items
        self.requested_usernames: list[str] = []

    def get_user_nfts(self, username: str) -> list[dict]:
        self.requested_usernames.append(username)
        return self._items


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

    def test_user_get_by_login_mail(self):
        with self.Session() as session:
            user = User(
                in_app_id="user-login",
                paymail="wallet-login",
                login_mail="user@example.com",
            )
            session.add(user)
            session.commit()

            found = User.get_by_login_mail(session, "user@example.com")
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.login_mail, "user@example.com")

    def test_user_login_mail_optional(self):
        with self.Session() as session:
            user_one = User(in_app_id="user-one", paymail="wallet-one")
            user_two = User(
                in_app_id="user-two",
                paymail="wallet-two",
                login_mail=None,
            )
            session.add_all([user_one, user_two])
            session.commit()

            refreshed = session.get(User, user_one.id)
            assert refreshed is not None
            self.assertIsNone(refreshed.login_mail)

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
            with patch(
                "nictbw.models.nft.generate_unique_nft_id",
                return_value="ABC-1234567890ab",
            ):
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
            self.assertEqual(ownership.unique_nft_id, "ABC-1234567890ab")
            self.assertEqual(ownership.acquired_at, nft.created_at)

    def test_generate_unique_id_retries_on_collision(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="collision@admin.com", password_hash="x")
            session.add(admin)
            session.flush()

            user = User(in_app_id="collision-user", paymail="collision-wallet")
            template = NFTTemplate(
                prefix="COL",
                name="Collision Template",
                category="cat",
                subcategory="sub",
                minted_count=1,
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add_all([user, template])
            session.flush()

            nft = NFT(
                template_id=template.id,
                prefix="COL",
                shared_key="existing",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(nft)
            session.flush()

            ownership = UserNFTOwnership(
                user_id=user.id,
                nft_id=nft.id,
                serial_number=0,
                unique_nft_id="COL-AAAAAAAAAAAA",
                acquired_at=now,
            )
            session.add(ownership)
            session.flush()

            from nictbw.models.utils import generate_unique_nft_id

            with patch(
                "nictbw.models.utils.secrets.choice",
                side_effect=list("A" * 12 + "B" * 12),
            ):
                generated = generate_unique_nft_id("COL", session=session)

            self.assertEqual(generated, "COL-BBBBBBBBBBBB")

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
            self.assertEqual(len({c.target_template_id for c in card.cells}), 9)
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

    def test_user_ensure_bingo_cells(self):
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
            tpl_unlock = NFTTemplate(
                prefix="UN",
                name="Unlock",
                category="cat",
                subcategory="subun",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
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
                for i in range(7)
            ]
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([tpl_trigger, tpl_unlock, user] + others)
            session.flush()

            nft_tr = tpl_trigger.instantiate_nft(shared_key="s1")
            nft_tr.issue_dbwise_to(session, user)
            session.commit()

            created = user.ensure_bingo_cards(session)
            session.commit()
            self.assertEqual(created, 1)

            card = user.bingo_cards[0]
            cell = next(c for c in card.cells if c.target_template_id == tpl_unlock.id)
            self.assertEqual(cell.state, "locked")

            nft_un = tpl_unlock.instantiate_nft(shared_key="s2")
            session.add(nft_un)
            session.flush()
            ownership = UserNFTOwnership(
                user_id=user.id,
                nft_id=nft_un.id,
                serial_number=0,
                unique_nft_id=f"{tpl_unlock.prefix}-A1B2C3D4E5F6",
                acquired_at=now,
            )
            session.add(ownership)
            session.flush()

            unlocked = user.ensure_bingo_cells(session)
            session.commit()
            self.assertEqual(unlocked, 1)
            self.assertEqual(cell.state, "unlocked")
            self.assertEqual(cell.nft_id, nft_un.id)
            self.assertEqual(cell.matched_ownership_id, ownership.id)

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
            ownership2 = UserNFTOwnership.get_by_user_and_nft(session, user.id, nft.id)
            self.assertIsNotNone(ownership2)
            assert ownership2 is not None
            self.assertEqual(ownership2.id, ownership.id)

    def test_sync_nfts_from_chain_requires_on_chain_id(self):
        with self.Session() as session:
            user = User(in_app_id="u-sync-none", paymail="wallet-none")
            session.add(user)
            session.flush()

            client = cast(ChainClient, DummyChainClient([]))

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                with self.assertRaises(ValueError):
                    user.sync_nfts_from_chain(session, client=client)

    def test_sync_nfts_from_chain_creates_local_records(self):
        created_at = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        updated_at = datetime(2024, 1, 2, 13, 0, tzinfo=timezone.utc)
        chain_items = [
            {
                "nft_origin": "origin-123",
                "metadata": {
                    "MAP": {
                        "subTypeData": {
                            "prefix": "CHAINPFX",
                            "sharedKey": "chain-shared",
                            "category": "event",
                            "subCategory": "booth-a",
                            "description": "Chain minted NFT",
                            "imageUrl": "https://example.com/image.png",
                            "name": "Chain Template Name",
                        }
                    }
                },
                "prefix": "IGNORED",
                "name": "Fallback Name",
                "nft_id": 99,
                "current_nft_location": "chain-vault",
                "created_at": "2024-01-01T12:00:00Z",
                "updated_at": "2024-01-02T13:00:00Z",
            }
        ]

        with self.Session() as session:
            admin = Admin(paymail="admin-sync@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            user = User(
                in_app_id="u-sync", paymail="wallet-sync", on_chain_id="chain-user"
            )
            session.add(user)
            session.flush()

            client_stub = DummyChainClient(chain_items)
            client = cast(ChainClient, client_stub)

            with patch(
                "nictbw.models.user.generate_unique_nft_id",
                return_value="CHAINPFX-AAAAAAAAAAAA",
            ):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    user.sync_nfts_from_chain(session, client=client)

            self.assertEqual(client_stub.requested_usernames, ["chain-user"])

            template = NFTTemplate.get_by_prefix(session, "CHAINPFX")
            self.assertIsNotNone(template)
            assert template is not None
            self.assertEqual(template.category, "event")
            self.assertEqual(template.subcategory, "booth-a")
            self.assertEqual(template.description, "Chain minted NFT")
            self.assertEqual(template.image_url, "https://example.com/image.png")
            self.assertEqual(template.minted_count, 1)
            self.assertEqual(template.created_by_admin_id, admin.id)

            nft = session.scalar(select(NFT).where(NFT.origin == "origin-123"))
            self.assertIsNotNone(nft)
            assert nft is not None
            self.assertEqual(nft.template_id, template.id)
            self.assertEqual(nft.shared_key, "chain-shared")
            self.assertEqual(nft.name, "Chain Template Name")
            self.assertEqual(nft.category, "event")
            self.assertEqual(nft.subcategory, "booth-a")
            self.assertEqual(nft.description, "Chain minted NFT")
            self.assertEqual(nft.image_url, "https://example.com/image.png")
            self.assertEqual(nft.current_location, "chain-vault")
            self.assertEqual(nft.id_on_chain, 99)
            self.assertEqual(nft.origin, "origin-123")
            self.assertEqual(
                nft.created_at.replace(tzinfo=None), created_at.replace(tzinfo=None)
            )
            self.assertEqual(
                nft.updated_at.replace(tzinfo=None), updated_at.replace(tzinfo=None)
            )

            ownership = session.scalar(
                select(UserNFTOwnership).where(UserNFTOwnership.user_id == user.id)
            )
            self.assertIsNotNone(ownership)
            assert ownership is not None
            self.assertEqual(ownership.nft_id, nft.id)
            self.assertEqual(ownership.serial_number, 0)
            self.assertEqual(ownership.unique_nft_id, "CHAINPFX-AAAAAAAAAAAA")
            self.assertEqual(
                ownership.acquired_at.replace(tzinfo=None),
                created_at.replace(tzinfo=None),
            )
            self.assertIsNotNone(ownership.other_meta)
            assert ownership.other_meta is not None
            meta = json.loads(ownership.other_meta)
            self.assertEqual(meta["shared_key"], "chain-shared")
            self.assertEqual(meta["image_url"], "https://example.com/image.png")

    def test_sync_nfts_from_chain_updates_existing_records(self):
        original_created = datetime(2024, 1, 5, 9, 0, tzinfo=timezone.utc)
        original_updated = datetime(2024, 1, 5, 10, 0, tzinfo=timezone.utc)
        chain_created = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
        chain_updated = datetime(2024, 1, 7, 18, 45, tzinfo=timezone.utc)
        chain_items = [
            {
                "nft_origin": "origin-xyz",
                "metadata": {
                    "MAP": {
                        "subTypeData": {
                            "prefix": "TPL",
                            "shared_key": "new-shared",
                            "category": "new-cat",
                            "subCategory": "new-sub",
                            "description": "Updated description",
                            "imageUrl": "https://example.com/new.png",
                            "name": "Updated NFT Name",
                        }
                    }
                },
                "name": "Fallback",
                "nft_id": 5,
                "current_nft_location": "new-location",
                "created_at": "2024-01-01T09:30:00Z",
                "updated_at": "2024-01-07T18:45:00Z",
                "unique_nft_id": "TPL-BBBBBBBBBBBB",
            }
        ]

        with self.Session() as session:
            admin = Admin(paymail="admin-update@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            user = User(
                in_app_id="u-sync-update",
                paymail="wallet-update",
                on_chain_id="chain-update",
            )
            session.add(user)
            session.flush()

            template = NFTTemplate(
                prefix="TPL",
                name="Template",
                category="old-cat",
                subcategory="old-sub",
                description="Old description",
                image_url="https://example.com/old.png",
                created_by_admin_id=admin.id,
                minted_count=1,
                created_at=original_created,
                updated_at=original_updated,
            )
            session.add(template)
            session.flush()

            nft = NFT(
                template_id=template.id,
                prefix="TPL",
                shared_key="old-shared",
                name="Old NFT Name",
                category="old-cat",
                subcategory="old-sub",
                description="Old description",
                image_url="https://example.com/old.png",
                created_by_admin_id=admin.id,
                id_on_chain=5,
                origin="origin-xyz",
                current_location="old-location",
                created_at=original_created,
                updated_at=original_updated,
            )
            session.add(nft)
            session.flush()

            ownership = UserNFTOwnership(
                user_id=user.id,
                nft_id=nft.id,
                serial_number=0,
                unique_nft_id="TPL-AAAAAAAAAAAA",
                acquired_at=datetime(2024, 1, 10, 9, 0, tzinfo=timezone.utc),
                other_meta=json.dumps({"old": "meta"}),
            )
            ownership.user = user
            session.add(ownership)
            session.flush()

            client_stub = DummyChainClient(chain_items)
            client = cast(ChainClient, client_stub)

            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                user.sync_nfts_from_chain(session, client=client)

            self.assertEqual(client_stub.requested_usernames, ["chain-update"])

            refreshed_nft = session.get(NFT, nft.id)
            assert refreshed_nft is not None
            self.assertEqual(refreshed_nft.shared_key, "new-shared")
            self.assertEqual(refreshed_nft.name, "Updated NFT Name")
            self.assertEqual(refreshed_nft.category, "new-cat")
            self.assertEqual(refreshed_nft.subcategory, "new-sub")
            self.assertEqual(refreshed_nft.description, "Updated description")
            self.assertEqual(refreshed_nft.image_url, "https://example.com/new.png")
            self.assertEqual(refreshed_nft.current_location, "new-location")
            self.assertEqual(
                refreshed_nft.created_at.replace(tzinfo=None),
                chain_created.replace(tzinfo=None),
            )
            self.assertEqual(
                refreshed_nft.updated_at.replace(tzinfo=None),
                chain_updated.replace(tzinfo=None),
            )

            refreshed_ownership = session.get(UserNFTOwnership, ownership.id)
            assert refreshed_ownership is not None
            self.assertEqual(refreshed_ownership.unique_nft_id, "TPL-BBBBBBBBBBBB")
            self.assertEqual(
                refreshed_ownership.acquired_at.replace(tzinfo=None),
                chain_created.replace(tzinfo=None),
            )
            self.assertIsNotNone(refreshed_ownership.other_meta)
            assert refreshed_ownership.other_meta is not None
            new_meta = json.loads(refreshed_ownership.other_meta)
            self.assertEqual(new_meta["description"], "Updated description")
            self.assertEqual(new_meta["subcategory"], "new-sub")

            refreshed_template = session.get(NFTTemplate, template.id)
            assert refreshed_template is not None
            self.assertEqual(refreshed_template.minted_count, 1)

    def test_prize_draw_models_roundtrip(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(paymail="draw-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            template = NFTTemplate(
                prefix="DRW",
                name="Draw Template",
                category="event",
                subcategory="game",
                created_by_admin_id=admin.id,
                minted_count=0,
            )
            user = User(in_app_id="draw-user", paymail="draw-wallet")
            session.add_all([template, user])
            session.flush()

            nft = template.instantiate_nft(shared_key="sk")
            nft.origin = "origin-seed"
            session.add(nft)
            session.flush()
            nft.issue_dbwise_to(session, user)

            draw_type = PrizeDrawType(
                internal_name="immediate",
                algorithm_key="hamming",
                default_threshold=0.5,
            )
            session.add(draw_type)
            session.flush()

            fetched_type = PrizeDrawType.get_by_internal_name(session, "immediate")
            self.assertIsNotNone(fetched_type)
            assert fetched_type is not None
            self.assertEqual(fetched_type.algorithm_key, "hamming")

            winning_number = PrizeDrawWinningNumber(
                draw_type_id=draw_type.id,
                value="101010",
            )
            session.add(winning_number)
            session.flush()

            result = PrizeDrawResult(
                draw_type_id=draw_type.id,
                winning_number_id=winning_number.id,
                user_id=user.id,
                nft_id=nft.id,
                ownership_id=user.ownerships[0].id,
                draw_number="101000",
                similarity_score=0.66,
                threshold_used=3.0,
                outcome="lose",
            )
            session.add(result)
            session.commit()

            retrieved = session.get(PrizeDrawResult, result.id)
            assert retrieved is not None
            self.assertEqual(retrieved.draw_type_id, draw_type.id)
            self.assertEqual(retrieved.winning_number_id, winning_number.id)
            self.assertEqual(retrieved.outcome, "lose")
            self.assertIsNotNone(retrieved.draw_type)
            assert retrieved.draw_type is not None
            self.assertEqual(retrieved.draw_type.results[0].id, result.id)
            self.assertIsNotNone(retrieved.winning_number)
            assert retrieved.winning_number is not None
            self.assertEqual(retrieved.winning_number.results[0].id, result.id)

            duplicate = PrizeDrawResult(
                draw_type_id=draw_type.id,
                winning_number_id=winning_number.id,
                user_id=user.id,
                nft_id=nft.id,
                draw_number="101111",
                outcome="win",
            )
            session.add(duplicate)
            with self.assertRaises(IntegrityError):
                session.commit()


if __name__ == "__main__":
    unittest.main()
