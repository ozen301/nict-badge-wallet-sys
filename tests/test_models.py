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
    NFTDefinition,
    NFTTemplate,
    NFTInstance,
    BingoCard,
    BingoCell,
    CouponTemplate,
    CouponStore,
    CouponInstance,
    NFTClaimRequest,
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

    def test_admin_get_by_email(self):
        with self.Session() as session:
            admin = Admin(email="admin@example.com", password_hash="x")
            session.add(admin)
            session.commit()

            found = Admin.get_by_email(session, "admin@example.com")
            self.assertIsNotNone(found)
            # help static type checkers understand `found` is not None
            assert found is not None
            self.assertEqual(found.email, "admin@example.com")

    def test_user_get_by_login_mail(self):
        with self.Session() as session:
            user = User(
                in_app_id="user-login",
                paymail="wallet-login",
                email="user@example.com",
            )
            session.add(user)
            session.commit()

            found = User.get_by_login_mail(session, "user@example.com")
            self.assertIsNotNone(found)
            assert found is not None
            self.assertEqual(found.email, "user@example.com")

    def test_user_login_mail_optional(self):
        with self.Session() as session:
            user_one = User(in_app_id="user-one", paymail="wallet-one")
            user_two = User(
                in_app_id="user-two",
                paymail="wallet-two",
                email=None,
            )
            session.add_all([user_one, user_two])
            session.commit()

            refreshed = session.get(User, user_one.id)
            assert refreshed is not None
            self.assertIsNone(refreshed.login_mail)

    def test_nft_count_and_get_by_prefix(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="a@b.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft_p = NFTDefinition(
                prefix="P",
                shared_key="shared-p",
                name="NFTDefinition-P",
                nft_type="default",
                category="cat",
                subcategory="subp",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            nft_q = NFTDefinition(
                prefix="Q",
                shared_key="shared-q",
                name="NFTDefinition-Q",
                nft_type="default",
                category="cat",
                subcategory="subq",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user_one = User(in_app_id="u1", paymail="wallet1")
            user_two = User(in_app_id="u2", paymail="wallet2")
            session.add_all([nft_p, nft_q, user_one, user_two])
            session.flush()

            nft_p.issue_dbwise_to_user(session, user_one)
            nft_p.issue_dbwise_to_user(session, user_two)
            nft_q.issue_dbwise_to_user(session, user_one)
            session.commit()

            count_p = NFTDefinition.count_instances_by_prefix(session, "P")
            self.assertEqual(count_p, 2)

            refreshed = session.scalar(select(NFTDefinition).where(NFTDefinition.prefix == "P"))
            self.assertIsNotNone(refreshed)
            assert refreshed is not None
            self.assertEqual(refreshed.prefix, "P")
            self.assertEqual(refreshed.minted_count, 2)

    def test_user_issue_nft_creates_ownership_and_increments(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="owner@admin.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft = NFTDefinition(
                prefix="ABC",
                shared_key="shared",
                name="Token",
                nft_type="default",
                category="cat",
                subcategory="sub",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            user_two = User(in_app_id="u2", paymail="wallet2")
            session.add_all([nft, user, user_two])
            session.flush()

            # Pre-condition
            self.assertEqual(nft.minted_count, 0)
            self.assertEqual(len(user.ownerships), 0)

            # Act
            with patch(
                "nictbw.models.nft.generate_unique_nft_id",
                return_value="ABC-1234567890ab",
            ):
                nft.issue_dbwise_to_user(session, user, acquired_at=nft.created_at)
            session.commit()

            # Verify minted_count incremented
            self.assertEqual(nft.minted_count, 1)
            # Ownership created and linked
            self.assertEqual(len(user.ownerships), 1)
            ownership: NFTInstance = user.ownerships[0]
            self.assertEqual(ownership.user_id, user.id)
            self.assertEqual(ownership.definition_id, nft.id)
            self.assertEqual(ownership.serial_number, 0)
            self.assertEqual(ownership.unique_nft_id, "ABC-1234567890ab")
            self.assertEqual(ownership.acquired_at, nft.created_at)

    def test_user_nfts_returns_instances(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="nfts-admin@example.com", password_hash="x")
            user = User(in_app_id="u-nfts", paymail="wallet-nfts")
            session.add_all([admin, user])
            session.flush()

            nft = NFTDefinition(
                prefix="USR",
                shared_key="shared",
                name="User NFT",
                nft_type="default",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(nft)
            session.flush()

            ownership = nft.issue_dbwise_to_user(session, user, nft_origin="origin-user")
            session.flush()

            self.assertEqual(len(user.nfts), 1)
            self.assertIsInstance(user.nfts[0], NFTInstance)
            self.assertEqual(user.nfts[0].id, ownership.id)

    def test_template_instantiate_nft_creates_instance(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="template-admin@example.com", password_hash="x")
            user = User(in_app_id="tpl-user", paymail="tpl-wallet")
            session.add_all([admin, user])
            session.flush()

            template = NFTTemplate(
                prefix="TPL-ONE",
                name="Template One",
                category="event",
                subcategory="shop",
                description="template desc",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(template)
            session.flush()

            instance = template.instantiate_nft(
                session,
                user,
                shared_key="tpl-shared",
                acquired_at=now,
                nft_origin="tpl-origin",
            )
            session.flush()

            self.assertIsInstance(instance, NFTInstance)
            self.assertEqual(instance.user_id, user.id)
            self.assertEqual(instance.definition.template_id, template.id)
            self.assertEqual(instance.definition.prefix, template.prefix)
            self.assertEqual(instance.nft_origin, "tpl-origin")

    def test_coupon_template_redeemed_count_and_max_redeem(self):
        with self.Session() as session:
            template = CouponTemplate(
                prefix="CPN1",
                name="Spring Discount",
                max_supply=5,
                max_redeem=3,
            )
            session.add(template)
            session.flush()

            coupon1 = CouponInstance(
                template=template,
                serial_number=1,
                coupon_code="CPN1-1",
            )
            coupon1.mark_redeemed()
            coupon2 = CouponInstance(
                template=template,
                serial_number=2,
                coupon_code="CPN1-2",
            )
            session.add_all([coupon1, coupon2])
            session.commit()

            reloaded = session.get(CouponTemplate, template.id)
            assert reloaded is not None
            self.assertEqual(reloaded.max_redeem, 3)
            self.assertEqual(reloaded.redeemed_count, 1)
            self.assertEqual(reloaded.remaining_redeem, 2)

    def test_coupon_template_default_display_definition_id(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="coupon-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            definition = NFTDefinition(
                prefix="CPN-DISP",
                shared_key="coupon-display",
                name="Coupon Display",
                nft_type="default",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(definition)
            session.flush()

            template = CouponTemplate(
                prefix="CPN-DISP-TPL",
                default_display_definition_id=definition.id,
            )
            session.add(template)
            session.commit()

            reloaded = session.get(CouponTemplate, template.id)
            assert reloaded is not None
            self.assertEqual(reloaded.default_display_definition_id, definition.id)

            with self.assertRaises(TypeError):
                CouponTemplate(prefix="CPN-OLD", default_display_nft_id=definition.id)

    def test_coupon_store_definition_fields(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="coupon-store-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            definition = NFTDefinition(
                prefix="CPN-STORE",
                shared_key="coupon-store",
                name="Coupon Store",
                nft_type="default",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(definition)
            session.flush()

            store = CouponStore(
                name="postcard-store-1",
                store_name="Postcard Store 1",
                definition_id=definition.id,
            )
            session.add(store)
            session.commit()

            reloaded = session.get(CouponStore, store.id)
            assert reloaded is not None
            self.assertEqual(reloaded.definition_id, definition.id)
            self.assertEqual(reloaded.definition.id, definition.id)

            with self.assertRaises(TypeError):
                CouponStore(name="legacy-store", store_name="Legacy Store", nft_id=definition.id)

    def test_nft_claim_request_definition_fields(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="claim-admin@example.com", password_hash="x")
            user = User(in_app_id="claim-user", paymail="claim-wallet")
            session.add_all([admin, user])
            session.flush()

            definition = NFTDefinition(
                prefix="CLM-DEF",
                shared_key="claim-definition",
                name="Claim Definition",
                nft_type="default",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(definition)
            session.flush()

            claim = NFTClaimRequest(
                tmp_id="tmp-claim-1",
                user_id=user.id,
                definition_id=definition.id,
                prefix=definition.prefix,
                shared_key=definition.shared_key,
            )
            session.add(claim)
            session.commit()

            reloaded = session.get(NFTClaimRequest, claim.id)
            assert reloaded is not None
            self.assertEqual(reloaded.definition_id, definition.id)
            self.assertEqual(reloaded.definition.id, definition.id)

            with self.assertRaises(TypeError):
                NFTClaimRequest(
                    tmp_id="tmp-claim-legacy",
                    user_id=user.id,
                    nft_id=definition.id,
                    prefix=definition.prefix,
                    shared_key=definition.shared_key,
                )

    def test_generate_unique_id_retries_on_collision(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="collision@admin.com", password_hash="x")
            session.add(admin)
            session.flush()

            user = User(in_app_id="collision-user", paymail="collision-wallet")
            session.add(user)
            session.flush()

            nft = NFTDefinition(
                prefix="COL",
                shared_key="existing",
                name="Collision",
                nft_type="default",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            session.add(nft)
            session.flush()

            ownership = NFTInstance(
                user_id=user.id,
                definition_id=nft.id,
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
            admin = Admin(email="admin@max.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft = NFTDefinition(
                prefix="SUP",
                shared_key="shared",
                name="Token",
                nft_type="default",
                category="cat",
                subcategory="sub",
                max_supply=1,
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            user_two = User(in_app_id="u2", paymail="wallet2")
            session.add_all([nft, user, user_two])
            session.flush()

            nft.issue_dbwise_to_user(session, user)

            with self.assertRaises(ValueError):
                nft.issue_dbwise_to_user(session, user_two)

    def test_bingo_completed_lines(self):
        card = BingoCard(user_id=1, issued_at=datetime.now(timezone.utc))
        # Prepare 9 cells, initially locked
        for i in range(9):
            cell = BingoCell(
                bingo_card_id=1,
                idx=i,
                target_definition_id=1,
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
            admin = Admin(email="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            prefixes = ["A", "B", "C", "X0", "X1", "X2", "X3", "X4", "X5"]
            definitions = []
            for prefix in prefixes:
                definitions.append(
                    NFTDefinition(
                        prefix=prefix,
                        shared_key=f"shared-{prefix}",
                        name=prefix,
                        nft_type="default",
                        category="cat",
                        subcategory=f"s{prefix.lower()}",
                        created_by_admin_id=admin.id,
                        created_at=now,
                        updated_at=now,
                    )
                )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all(definitions + [user])
            session.flush()

            card = BingoCard(user_id=user.id, issued_at=now)
            session.add(card)
            session.flush()

            cells = [
                BingoCell(bingo_card_id=card.id, idx=0, target_definition_id=definitions[0].id),
                BingoCell(bingo_card_id=card.id, idx=1, target_definition_id=definitions[1].id),
                BingoCell(bingo_card_id=card.id, idx=2, target_definition_id=definitions[2].id),
            ]
            for i in range(3, 9):
                cells.append(
                    BingoCell(
                        bingo_card_id=card.id,
                        idx=i,
                        target_definition_id=definitions[i].id,
                    )
                )
            for c in cells:
                card.cells.append(c)
                session.add(c)
            session.flush()

            definitions[0].issue_dbwise_to_user(session, user)
            definitions[1].issue_dbwise_to_user(session, user)
            definitions[2].issue_dbwise_to_user(session, user)
            session.commit()

            self.assertEqual(card.state, "active")
            self.assertIsNone(card.completed_at)

            for i in range(3, 9):
                definitions[i].issue_dbwise_to_user(session, user)
            session.commit()

            self.assertEqual(card.state, "completed")
            self.assertIsNotNone(card.completed_at)
            self.assertTrue(all(c.state == "unlocked" for c in card.cells))
            self.assertTrue(all(c.matched_ownership_id is not None for c in card.cells))

    def test_user_unlock_cells_for_definition(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft_main = NFTDefinition(
                prefix="T",
                shared_key="shared-t",
                name="TokenT",
                nft_type="default",
                category="cat",
                subcategory="subt",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            nft_other = NFTDefinition(
                prefix="O",
                shared_key="shared-o",
                name="Other",
                nft_type="default",
                category="cat",
                subcategory="subo",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([nft_main, nft_other, user])
            session.flush()

            nft_main.issue_dbwise_to_user(session, user)

            card = BingoCard(user_id=user.id, issued_at=now)
            session.add(card)
            session.flush()

            cells = [
                BingoCell(bingo_card_id=card.id, idx=0, target_definition_id=nft_main.id)
            ]
            for i in range(1, 9):
                cells.append(
                    BingoCell(
                        bingo_card_id=card.id,
                        idx=i,
                        target_definition_id=nft_other.id,
                    )
                )
            for c in cells:
                card.cells.append(c)
                session.add(c)
            session.flush()

            cell = cells[0]
            self.assertEqual(cell.state, "locked")

            result = user.unlock_cells_for_definition(session, nft_main)
            self.assertTrue(result)
            self.assertEqual(cell.state, "unlocked")
            self.assertEqual(cell.matched_ownership_id, user.ownerships[0].id)

            # Reset and test using the NFTDefinition's ID
            cell.state = "locked"
            cell.definition_id = None
            cell.matched_ownership_id = None
            session.flush()

            result = user.unlock_cells_for_definition(session, nft_main.id)
            self.assertTrue(result)
            self.assertEqual(cell.state, "unlocked")
            self.assertEqual(cell.matched_ownership_id, user.ownerships[0].id)

    def test_bingocard_generate_for_user(self):
        now = datetime.now(timezone.utc)
        rng = random.Random(0)
        with self.Session() as session:
            admin = Admin(email="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            definitions = [
                NFTDefinition(
                    prefix=f"T{i}",
                    shared_key=f"shared-{i}",
                    name=f"T{i}",
                    nft_type="default",
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
            session.add_all(definitions + [user])
            session.flush()

            definitions[0].issue_dbwise_to_user(session, user)
            session.commit()

            card = BingoCard.generate_for_user(
                session=session,
                user=user,
                center_definition=definitions[0],
                rng=rng,
            )
            self.assertEqual(len(card.cells), 9)
            self.assertEqual(len({c.target_definition_id for c in card.cells}), 9)
            center = next(c for c in card.cells if c.idx == 4)
            self.assertEqual(center.state, "unlocked")

    def test_user_ensure_bingo_cards(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            trigger = NFTDefinition(
                prefix="TR",
                shared_key="shared-tr",
                name="Trigger",
                nft_type="default",
                category="cat",
                subcategory="subtr",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
                triggers_bingo_card=True,
            )
            others = [
                NFTDefinition(
                    prefix=f"O{i}",
                    shared_key=f"shared-o{i}",
                    name=f"O{i}",
                    nft_type="default",
                    category="cat",
                    subcategory=f"so{i}",
                    created_by_admin_id=admin.id,
                    created_at=now,
                    updated_at=now,
                )
                for i in range(8)
            ]
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([trigger, user] + others)
            session.flush()

            trigger.issue_dbwise_to_user(session, user)
            session.commit()

            created = user.ensure_bingo_cards(session)
            session.commit()
            self.assertEqual(created, 1)
            self.assertEqual(len(user.bingo_cards), 1)

    def test_user_ensure_bingo_cells(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft_trigger = NFTDefinition(
                prefix="TR",
                shared_key="shared-tr",
                name="Trigger",
                nft_type="default",
                category="cat",
                subcategory="subtr",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
                triggers_bingo_card=True,
            )
            nft_unlock = NFTDefinition(
                prefix="UN",
                shared_key="shared-un",
                name="Unlock",
                nft_type="default",
                category="cat",
                subcategory="subun",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            others = [
                NFTDefinition(
                    prefix=f"O{i}",
                    shared_key=f"shared-o{i}",
                    name=f"O{i}",
                    nft_type="default",
                    category="cat",
                    subcategory=f"so{i}",
                    created_by_admin_id=admin.id,
                    created_at=now,
                    updated_at=now,
                )
                for i in range(7)
            ]
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([nft_trigger, nft_unlock, user] + others)
            session.flush()

            nft_trigger.issue_dbwise_to_user(session, user)
            session.commit()

            created = user.ensure_bingo_cards(session)
            session.commit()
            self.assertEqual(created, 1)

            card = user.bingo_cards[0]
            cell = next(c for c in card.cells if c.target_definition_id == nft_unlock.id)
            self.assertEqual(cell.state, "locked")

            ownership = nft_unlock.issue_dbwise_to_user(
                session,
                user,
                unique_nft_id=f"{nft_unlock.prefix}-A1B2C3D4E5F6",
                acquired_at=now,
            )

            unlocked = user.ensure_bingo_cells(session)
            session.commit()
            self.assertEqual(unlocked, 0)
            self.assertEqual(cell.state, "unlocked")
            self.assertEqual(cell.definition_id, nft_unlock.id)
            self.assertEqual(cell.matched_ownership_id, ownership.id)

    def test_ownership_get_by_user_and_definition(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft = NFTDefinition(
                prefix="T",
                shared_key="shared-t",
                name="TokenT",
                nft_type="default",
                category="cat",
                subcategory="subt",
                created_by_admin_id=admin.id,
                created_at=now,
                updated_at=now,
            )
            user = User(in_app_id="u1", paymail="wallet1")
            session.add_all([nft, user])
            session.flush()

            nft.issue_dbwise_to_user(session, user)
            session.commit()

            ownership = NFTInstance.get_by_user_and_definition(session, user, nft)
            self.assertIsNotNone(ownership)
            assert ownership is not None
            self.assertEqual(ownership.user_id, user.id)
            self.assertEqual(ownership.definition_id, nft.id)

            # Also verify lookup works with IDs
            ownership2 = NFTInstance.get_by_user_and_definition(session, user.id, nft.id)
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
                            "description": "Chain minted NFTDefinition",
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
            admin = Admin(email="admin-sync@example.com", password_hash="x")
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
                "nictbw.models.utils.generate_unique_nft_id",
                return_value="CHAINPFX-AAAAAAAAAAAA",
            ):
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore", UserWarning)
                    user.sync_nfts_from_chain(session, client=client)

            self.assertEqual(client_stub.requested_usernames, ["chain-user"])

            nft = session.scalar(select(NFTDefinition).where(NFTDefinition.prefix == "CHAINPFX"))
            self.assertIsNotNone(nft)
            assert nft is not None
            self.assertEqual(nft.shared_key, "chain-shared")
            self.assertEqual(nft.name, "Chain Template Name")
            self.assertEqual(nft.category, "event")
            self.assertEqual(nft.subcategory, "booth-a")
            self.assertEqual(nft.description, "Chain minted NFTDefinition")
            self.assertEqual(nft.image_url, "https://example.com/image.png")
            self.assertEqual(nft.minted_count, 1)
            self.assertEqual(nft.created_by_admin_id, admin.id)
            self.assertEqual(
                nft.created_at.replace(tzinfo=None), created_at.replace(tzinfo=None)
            )
            self.assertEqual(
                nft.updated_at.replace(tzinfo=None), updated_at.replace(tzinfo=None)
            )

            ownership = session.scalar(
                select(NFTInstance).where(NFTInstance.user_id == user.id)
            )
            self.assertIsNotNone(ownership)
            assert ownership is not None
            self.assertEqual(ownership.definition_id, nft.id)
            self.assertEqual(ownership.serial_number, 0)
            self.assertEqual(ownership.unique_nft_id, "CHAINPFX-AAAAAAAAAAAA")
            self.assertEqual(ownership.nft_origin, "origin-123")
            self.assertEqual(ownership.current_nft_location, "chain-vault")
            self.assertEqual(ownership.blockchain_nft_id, 99)
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
                            "name": "Updated NFTDefinition Name",
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
            admin = Admin(email="admin-update@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            user = User(
                in_app_id="u-sync-update",
                paymail="wallet-update",
                on_chain_id="chain-update",
            )
            session.add(user)
            session.flush()

            nft = NFTDefinition(
                prefix="TPL",
                shared_key="old-shared",
                name="Old NFTDefinition Name",
                nft_type="default",
                category="old-cat",
                subcategory="old-sub",
                description="Old description",
                image_url="https://example.com/old.png",
                created_by_admin_id=admin.id,
                created_at=original_created,
                updated_at=original_updated,
            )
            session.add(nft)
            session.flush()

            ownership = NFTInstance(
                user_id=user.id,
                definition_id=nft.id,
                serial_number=0,
                unique_nft_id="TPL-AAAAAAAAAAAA",
                acquired_at=datetime(2024, 1, 10, 9, 0, tzinfo=timezone.utc),
                other_meta=json.dumps({"old": "meta"}),
                nft_origin="origin-xyz",
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

            refreshed_nft = session.get(NFTDefinition, nft.id)
            assert refreshed_nft is not None
            self.assertEqual(refreshed_nft.shared_key, "new-shared")
            self.assertEqual(refreshed_nft.name, "Updated NFTDefinition Name")
            self.assertEqual(refreshed_nft.category, "new-cat")
            self.assertEqual(refreshed_nft.subcategory, "new-sub")
            self.assertEqual(refreshed_nft.description, "Updated description")
            self.assertEqual(refreshed_nft.image_url, "https://example.com/new.png")
            self.assertEqual(
                refreshed_nft.created_at.replace(tzinfo=None),
                chain_created.replace(tzinfo=None),
            )
            self.assertEqual(
                refreshed_nft.updated_at.replace(tzinfo=None),
                chain_updated.replace(tzinfo=None),
            )

            refreshed_ownership = session.get(NFTInstance, ownership.id)
            assert refreshed_ownership is not None
            self.assertEqual(refreshed_ownership.unique_nft_id, "TPL-BBBBBBBBBBBB")
            self.assertEqual(refreshed_ownership.nft_origin, "origin-xyz")
            self.assertEqual(refreshed_ownership.current_nft_location, "new-location")
            self.assertEqual(
                refreshed_ownership.acquired_at.replace(tzinfo=None),
                chain_created.replace(tzinfo=None),
            )
            self.assertIsNotNone(refreshed_ownership.other_meta)
            assert refreshed_ownership.other_meta is not None
            new_meta = json.loads(refreshed_ownership.other_meta)
            self.assertEqual(new_meta["description"], "Updated description")
            self.assertEqual(new_meta["subcategory"], "new-sub")

    def test_prize_draw_models_roundtrip(self):
        now = datetime.now(timezone.utc)
        with self.Session() as session:
            admin = Admin(email="draw-admin@example.com", password_hash="x")
            session.add(admin)
            session.flush()

            nft = NFTDefinition(
                prefix="DRW",
                shared_key="shared",
                name="Draw NFTDefinition",
                nft_type="default",
                category="event",
                subcategory="game",
                created_by_admin_id=admin.id,
            )
            user = User(in_app_id="draw-user", paymail="draw-wallet")
            session.add_all([nft, user])
            session.flush()

            ownership = nft.issue_dbwise_to_user(
                session, user, nft_origin="origin-seed", acquired_at=now
            )

            draw_type = PrizeDrawType(
                internal_name="immediate",
                algorithm_key="sha256_hex_proximity",
                default_threshold=0.5,
            )
            session.add(draw_type)
            session.flush()

            fetched_type = PrizeDrawType.get_by_internal_name(session, "immediate")
            self.assertIsNotNone(fetched_type)
            assert fetched_type is not None
            self.assertEqual(fetched_type.algorithm_key, "sha256_hex_proximity")

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
                definition_id=nft.id,
                ownership_id=ownership.id,
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
                definition_id=nft.id,
                draw_number="101111",
                outcome="win",
            )
            session.add(duplicate)
            with self.assertRaises(IntegrityError):
                session.commit()


if __name__ == "__main__":
    unittest.main()
