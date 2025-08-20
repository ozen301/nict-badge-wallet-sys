from __future__ import annotations
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone

# ensure project root on sys.path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from app.db.engine import make_engine, get_sessionmaker
from app.models import (
    Base,
    Admin,
    User,
    NFTCondition,
    NFT,
    UserNFTOwnership,
    BingoCard,
    BingoCell,
)


def main() -> None:
    """Seed the development database with sample data."""
    engine = make_engine()

    # Drop and recreate all tables. SQLite struggles with cyclic foreign-key
    # dependencies during DROP, so temporarily disable foreign key checks to
    # ensure a clean reset of the schema.
    with engine.connect() as conn:
        conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
        Base.metadata.drop_all(bind=conn)
        conn.exec_driver_sql("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)
    Session = get_sessionmaker(engine)

    now = datetime.now(timezone.utc)

    with Session.begin() as session:
        # Admin
        admin = Admin(
            paymail="admin@example.com",
            password_hash="dev-hash",
            name="DevAdmin",
            role="superuser",
            created_at=now,
            updated_at=now,
        )
        session.add(admin)
        session.flush()

        # Users
        user1 = User(
            in_app_id="user_01",
            wallet="wallet_01",
            nickname="Alice",
            created_at=now,
            updated_at=now,
        )
        user2 = User(
            in_app_id="user_02",
            wallet="wallet_02",
            nickname="Bob",
            created_at=now,
            updated_at=now,

        )
        session.add_all([user1, user2])
        session.flush()

        # NFT condition
        condition = NFTCondition(
            start_time=now,
            end_time=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        )
        session.add(condition)
        session.flush()

        # NFTs
        nft1 = NFT(
            prefix="prefix-1",
            shared_key="shared-key-1",
            name="Game Entry Badge",
            nft_type="default",
            description="Issued for attending the game",
            condition_id=condition.id,
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        nft2 = NFT(
            prefix="prefix-2",
            shared_key="shared-key-2",
            name="Restaurant Visit Badge",
            nft_type="event",
            description="Issued for visiting partner restaurant #1",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        nft3 = NFT(
            prefix="prefix-3",
            shared_key="shared-key-3",
            name="Coffee Shop Badge",
            nft_type="event",
            description="Issued for visiting partner restaurant #2",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        nft4 = NFT(
            prefix="prefix-4",
            shared_key="shared-key-4",
            name="Museum Visit Badge",
            nft_type="event",
            description="Issued for visiting partner restaurant #3",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        nft5 = NFT(
            prefix="prefix-5",
            shared_key="shared-key-5",
            name="Library Badge",
            nft_type="event",
            description="Issued for visiting partner restaurant #4",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        nft6 = NFT(
            prefix="prefix-6",
            shared_key="shared-key-6",
            name="Park Badge",
            nft_type="event",
            description="Issued for visiting partner restaurant #5",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        nft7 = NFT(
            prefix="prefix-7",
            shared_key="shared-key-7",
            name="Cinema Badge",
            nft_type="event",
            description="Issued for attending partner restaurant #6",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        nft8 = NFT(
            prefix="prefix-8",
            shared_key="shared-key-8",
            name="Bookstore Badge",
            nft_type="event",
            description="Issued for visiting partner restaurant #7",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        nft9 = NFT(
            prefix="prefix-9",
            shared_key="shared-key-9",
            name="Gym Badge",
            nft_type="event",
            description="Issued for visiting partner restaurant #8",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )



        session.add_all([nft1, nft2, nft3, nft4, nft5, nft6, nft7, nft8, nft9])
        session.flush()

        # Ownerships
        own1 = UserNFTOwnership(
            user_id=user1.id,
            nft_id=nft1.id,
            serial_number=1,
            unique_nft_id="nft1-0001",
            acquired_at=now,
        )
        own2 = UserNFTOwnership(
            user_id=user1.id,
            nft_id=nft2.id,
            serial_number=1,
            unique_nft_id="nft2-0001",
            acquired_at=now,
        )
        session.add_all([own1, own2])
        session.flush()

        # Bingo card for user1
        card = BingoCard(
            user_id=user1.id,
            issued_at=now,
            state="active",
        )
        session.add(card)
        session.flush()

        # Bingo cells
        cells: list[BingoCell] = []
        nft_list = [nft2, nft3, nft4, nft5, nft1, nft6, nft7, nft8, nft9]
        for idx in range(9):
            if idx == 4:
                cell = BingoCell(
                    bingo_card_id=card.id,
                    idx=idx,
                    target_nft_id=nft1.id,
                    matched_ownership_id=own1.id,
                    state="unlocked",
                    unlocked_at=now,
                )
            else:
                cell = BingoCell(
                    bingo_card_id=card.id,
                    idx=idx,
                    target_nft_id=nft_list[idx].id,
                    state="locked",
                )
            cells.append(cell)
        session.add_all(cells)

    print("Development database seeded.")


if __name__ == "__main__":
    main()
