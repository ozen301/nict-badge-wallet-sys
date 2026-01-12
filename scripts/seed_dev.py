from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from nictbw.db.engine import make_engine
from nictbw.models import (
    Base,
    Admin,
    User,
    NFTCondition,
    NFT,
    CouponTemplate,
    NFTCouponBinding,
    CouponInstance,
)


def main() -> None:
    """Seed the development database with sample data."""
    engine = make_engine()

    if engine.dialect.name == "sqlite":
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
            Base.metadata.drop_all(bind=conn)
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
    else:
        Base.metadata.drop_all(bind=engine)

    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    now = datetime.now(timezone.utc)

    with Session.begin() as session:
        admin = Admin(
            email="admin@example.com",
            password_hash="dev-hash",
            name="nictbw_admin",
            role="superuser",
            created_at=now,
            updated_at=now,
        )
        session.add(admin)
        session.flush()

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

        condition = NFTCondition(
            start_time=now,
            end_time=now + timedelta(days=30),
            created_at=now,
            updated_at=now,
        )
        session.add(condition)
        session.flush()

        nft_specs = [
            {
                "prefix": "prefix-1",
                "name": "Game Watching Badge",
                "category": "game",
                "subcategory": "Sendai89ers_2025-09-11",
                "description": "Issued for watching the game.",
                "triggers_bingo_card": True,
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/1/10/Basketball_through_hoop.jpg/330px-Basketball_through_hoop.jpg",
            },
            {
                "prefix": "prefix-2",
                "name": "Game Watching Badge",
                "category": "game",
                "subcategory": "Sendai89ers_2025-09-12",
                "description": "Issued for watching the game.",
                "triggers_bingo_card": True,
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/4/4e/Basketball_Goal.jpg",
            },
            {
                "prefix": "prefix-3",
                "name": "ExampleShop-1 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-1",
                "description": "Issued for visiting partner restaurant #1.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/8/85/Intel_logo_2023.svg",
            },
            {
                "prefix": "prefix-4",
                "name": "ExampleShop-2 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-2",
                "description": "Issued for visiting partner restaurant #2.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/4/4e/Pleiades_large.jpg",
            },
            {
                "prefix": "prefix-5",
                "name": "ExampleShop-3 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-3",
                "description": "Issued for visiting partner restaurant #3.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/3/3c/Shaki_waterfall.jpg",
            },
            {
                "prefix": "prefix-6",
                "name": "ExampleShop-4 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-4",
                "description": "Issued for visiting partner restaurant #4.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/6/6f/Great_Wave_off_Kanagawa2.jpg",
            },
            {
                "prefix": "prefix-7",
                "name": "ExampleShop-5 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-5",
                "description": "Issued for visiting partner restaurant #5.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/6/64/Paris_Skyline.jpg",
            },
            {
                "prefix": "prefix-8",
                "name": "ExampleShop-6 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-6",
                "description": "Issued for visiting partner restaurant #6.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/5/50/Vd-Orig.png",
            },
            {
                "prefix": "prefix-9",
                "name": "ExampleShop-7 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-7",
                "description": "Issued for visiting partner restaurant #7.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/3/3a/Cat03.jpg",
            },
            {
                "prefix": "prefix-10",
                "name": "ExampleShop-8 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-8",
                "description": "Issued for visiting partner restaurant #8.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/5/57/Tubifex_worms.gif",
            },
            {
                "prefix": "prefix-11",
                "name": "ExampleShop-9 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-9",
                "description": "Issued for visiting partner restaurant #9.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/5/5b/Plotter_XY_1983_Robotron.jpg",
            },
            {
                "prefix": "prefix-12",
                "name": "ExampleShop-10 Badge",
                "category": "restaurant",
                "subcategory": "ExampleShopName-10",
                "description": "Issued for visiting partner restaurant #10.",
                "image_url": "https://upload.wikimedia.org/wikipedia/commons/3/3f/JPEG_example_flower.jpg",
            },
        ]

        nfts: list[NFT] = []
        for spec in nft_specs:
            nfts.append(
                NFT(
                    prefix=spec["prefix"],
                    shared_key=f"{spec['prefix']}-shared",
                    name=spec["name"],
                    nft_type="default",
                    category=spec["category"],
                    subcategory=spec["subcategory"],
                    description=spec["description"],
                    image_url=spec.get("image_url"),
                    condition_id=condition.id,
                    triggers_bingo_card=spec.get("triggers_bingo_card", False),
                    created_by_admin_id=admin.id,
                    created_at=now,
                    updated_at=now,
                )
            )
        session.add_all(nfts)
        session.flush()

        coupon_tpl1 = CouponTemplate(
            prefix="CPN1",
            name="Basketball Coupon",
            description="Sample coupon template",
            max_supply=10,
            max_redeem=10,
            expiry_days=30,
            store_name="Sample Store 1",
        )
        coupon_tpl2 = CouponTemplate(
            prefix="CPN2",
            name="Restaurant Coupon",
            description="Sample coupon template",
            max_supply=5,
            max_redeem=5,
            expiry_days=14,
            store_name="Sample Store 2",
        )
        session.add_all([coupon_tpl1, coupon_tpl2])
        session.flush()

        binding1 = NFTCouponBinding(
            nft_id=nfts[0].id,
            template_id=coupon_tpl1.id,
            quantity_per_claim=1,
            active=True,
        )
        binding2 = NFTCouponBinding(
            nft_id=nfts[1].id,
            template_id=coupon_tpl2.id,
            quantity_per_claim=1,
            active=True,
        )
        session.add_all([binding1, binding2])
        session.flush()

        # Issue sample ownerships
        nfts[0].issue_dbwise_to(session, user1, nft_origin="seed-origin-1")
        nfts[1].issue_dbwise_to(session, user1, nft_origin="seed-origin-2")

        # Issue sample coupon instances
        coupon1 = CouponInstance(
            template=coupon_tpl1,
            serial_number=1,
            coupon_code=f"{coupon_tpl1.prefix}-000001",
            expiry=now + timedelta(days=coupon_tpl1.expiry_days or 30),
            store_name=coupon_tpl1.store_name,
        )
        coupon2 = CouponInstance(
            template=coupon_tpl2,
            serial_number=1,
            coupon_code=f"{coupon_tpl2.prefix}-000001",
            expiry=now + timedelta(days=coupon_tpl2.expiry_days or 14),
            store_name=coupon_tpl2.store_name,
        )
        session.add_all([coupon1, coupon2])
        coupon_tpl1.next_serial = 2
        coupon_tpl2.next_serial = 2


if __name__ == "__main__":
    main()
