from .base import Base

# import models so Alembic/autoloaders can discover mappers
from .admin import Admin  # noqa: F401
from .user import User  # noqa: F401
from .nft import NFTCondition, NFTTemplate, NFT, NFTDefinition  # noqa: F401
from .ownership import UserNFTOwnership, NFTInstance  # noqa: F401
from .bingo import (  # noqa: F401
    BingoPeriod,
    BingoPeriodReward,
    BingoCard,
    BingoCardIssueTask,
    BingoCell,
    PreGeneratedBingoCard,
)
from .coupon import (  # noqa: F401
    CouponTemplate,
    NFTCouponBinding,
    CouponInstance,
    CouponStore,
    CouponPlayer,
    CouponPlayerStoreInventory,
)
from .prize_draw import (  # noqa: F401
    PrizeDrawType,
    PrizeDrawWinningNumber,
    PrizeDrawResult,
    RaffleEvent,
    RaffleEntry,
)
from .misc import (  # noqa: F401
    NFTClaimRequest,
    UserActivityEvent,
    ExternalAccount,
    AppBanner,
    PreMintedUser,
    SystemConfiguration,
)

__all__ = [
    "Base",
    "Admin",
    "User",
    "NFTCondition",
    "NFTTemplate",
    "NFT",
    "NFTDefinition",
    "UserNFTOwnership",
    "NFTInstance",
    "BingoPeriod",
    "BingoPeriodReward",
    "BingoCard",
    "BingoCardIssueTask",
    "BingoCell",
    "PreGeneratedBingoCard",
    "CouponTemplate",
    "NFTCouponBinding",
    "CouponInstance",
    "CouponStore",
    "CouponPlayer",
    "CouponPlayerStoreInventory",
    "PrizeDrawType",
    "PrizeDrawWinningNumber",
    "PrizeDrawResult",
    "RaffleEvent",
    "RaffleEntry",
    "NFTClaimRequest",
    "UserActivityEvent",
    "ExternalAccount",
    "AppBanner",
    "PreMintedUser",
    "SystemConfiguration",
]
