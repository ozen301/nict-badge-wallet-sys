from sqlalchemy.orm import DeclarativeBase
from nictbw.db.metadata import metadata_obj

class Base(DeclarativeBase):
    metadata = metadata_obj

# import models so Alembic/autoloaders can discover mappers
from .admin import Admin  # noqa: F401
from .user import User  # noqa: F401
from .nft import NFTCondition, NFT  # noqa: F401
from .ownership import UserNFTOwnership  # noqa: F401
from .bingo import BingoCard, BingoCell  # noqa: F401
from .chain import BlockchainTransaction  # noqa: F401
from .audit import AuditLog  # noqa: F401
