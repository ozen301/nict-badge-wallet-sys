from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker
from nictbw.db.engine import make_engine
from nictbw.models import (
    Base,
    Admin,
    User,
    NFTCondition,
    NFTTemplate,
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
    Session = sessionmaker(bind=engine)

    now = datetime.now(timezone.utc)

    with Session.begin() as session:
        # Admin
        admin = Admin(
            paymail="admin@example.com",
            password_hash="dev-hash",
            name="nictbw_admin",
            role="superuser",
            created_at=now,
            updated_at=now,
        )
        session.add(admin)
        session.flush()

        # Users
        user1 = User(
            in_app_id="user_01",
            paymail="paymail_01",
            nickname="Alice",
            created_at=now,
            updated_at=now,
        )
        user2 = User(
            in_app_id="user_02",
            paymail="paymail_02",
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

        # NFT templates
        tpl1 = NFTTemplate(
            prefix="prefix-1",
            name="Game Watching Badge",
            category="game",
            subcategory="Sendai89ers_2025-09-11",
            description="Description to be shown in the mobile app goes here, e.g. issued for watching the game.",
            default_condition=condition,
            created_by_admin_id=admin.id,
            triggers_bingo_card=True,
            created_at=now,
            updated_at=now,
        )
        tpl2 = NFTTemplate(
            prefix="prefix-2",
            name="Game Watching Badge",
            category="game",
            subcategory="Sendai89ers_2025-09-12",
            description="Description to be shown in the mobile app goes here, e.g. issued for watching the game.",
            created_by_admin_id=admin.id,
            triggers_bingo_card=True,
            created_at=now,
            updated_at=now,
        )
        tpl3 = NFTTemplate(
            prefix="prefix-3",
            name="ExampleShop-1 Badge",
            category="restaurant",
            subcategory="ExampleShopName-1",
            description="Description to be shown in the mobile app goes here, e.g. issued for visiting partner restaurant #1.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl4 = NFTTemplate(
            prefix="prefix-4",
            name="ExampleShop-2 Badge",
            category="restaurant",
            subcategory="ExampleShopName-2",
            description="Description to be shown in the mobile app goes here, e.g. issued for visiting partner restaurant #2.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl5 = NFTTemplate(
            prefix="prefix-5",
            name="ExampleShop-3 Badge",
            category="restaurant",
            subcategory="ExampleShopName-3",
            description="Description to be shown in the mobile app goes here, e.g. issued for visiting partner restaurant #3.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl6 = NFTTemplate(
            prefix="prefix-6",
            name="ExampleShop-4 Badge",
            category="restaurant",
            subcategory="ExampleShopName-4",
            description="Description to be shown in the mobile app goes here, e.g. issued for visiting partner restaurant #4.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl7 = NFTTemplate(
            prefix="prefix-7",
            name="ExampleShop-5 Badge",
            category="restaurant",
            subcategory="ExampleShopName-5",
            description="Description to be shown in the mobile app goes here, e.g. issued for attending partner restaurant #5.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl8 = NFTTemplate(
            prefix="prefix-8",
            name="ExampleEvent-1 Badge",
            category="event",
            subcategory="ExampleEventName-1",
            description="Description to be shown in the mobile app goes here, e.g. issued for attending partner event #1.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl9 = NFTTemplate(
            prefix="prefix-9",
            name="ExampleEvent-2 Badge",
            category="event",
            subcategory="ExampleEventName-2",
            description="Description to be shown in the mobile app goes here, e.g. issued for attending partner event #2.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl10 = NFTTemplate(
            prefix="prefix-10",
            name="ExampleEvent-3 Badge",
            category="event",
            subcategory="ExampleEventName-3",
            description="Description to be shown in the mobile app goes here, e.g. issued for attending partner event #3.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl11 = NFTTemplate(
            prefix="prefix-11",
            name="ExampleEvent-4 Badge",
            category="event",
            subcategory="ExampleEventName-4",
            description="Description to be shown in the mobile app goes here, e.g. issued for attending partner event #4.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )
        tpl12 = NFTTemplate(
            prefix="prefix-12",
            name="ExampleShop-6 Badge",
            category="restaurant",
            subcategory="ExampleShopName-6",
            description="Description to be shown in the mobile app goes here, e.g. issued for visiting partner restaurant #6.",
            created_by_admin_id=admin.id,
            created_at=now,
            updated_at=now,
        )

        session.add_all(
            [tpl1, tpl2, tpl3, tpl4, tpl5, tpl6, tpl7, tpl8, tpl9, tpl10, tpl11, tpl12]
        )
        session.flush()

        # Issue NFTs to user1
        nft1 = tpl1.instantiate_nft(shared_key="shared-key-1")
        nft1.issue_dbwise_to(session, user1)
        nft2 = tpl2.instantiate_nft(shared_key="shared-key-2")
        nft2.issue_dbwise_to(session, user1)
        session.flush()

        user1.ensure_bingo_cards(session)
        session.flush()

    print("Development database seeded.")


if __name__ == "__main__":
    main()
