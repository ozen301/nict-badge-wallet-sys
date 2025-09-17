from typing import TYPE_CHECKING
from sqlalchemy.orm import Session

from .models.user import User

if TYPE_CHECKING:
    from .models import Admin, NFT, NFTTemplate


def register_user(session: Session, user: User) -> User:
    """Create a new user in the database and trigger its on-chain registration."""
    if user.id is not None:
        raise ValueError("User already has an ID, cannot register again.")

    session.add(user)
    user.register_on_chain(session)
    session.flush()

    return user


def create_and_issue_nft(
    session: Session, user: User, shared_key: str, nft_template: "NFTTemplate"
) -> "NFT":
    """Instantiate, mint, and assign an NFT generated from ``nft_template``.

    The supplied ``user`` must have a paymail so the NFT can be minted on-chain.

    This function performs the following steps:
    1. Instantiates an NFT from the template using ``shared_key``.
    2. Mints the NFT on-chain. Updates the NFT instance with on-chain metadata.
    3. Stores the NFT in the database.
    4. Links it to the user. If the template is configured to trigger bingo cards,
    a fresh card is generated for the user.

    Returns:
        The fully populated ``NFT`` instance after it has been minted and stored.
    """
    from .models.bingo import BingoCard

    if user.paymail is None:
        raise ValueError("User must have a paymail to receive an NFT.")

    # Instantiate the NFT
    nft = nft_template.instantiate_nft(shared_key=shared_key)
    create_new_bingo_card: bool = nft_template.triggers_bingo_card

    # Mint on-chain; this updates the NFT instance with on-chain metadata.
    nft.mint_on_chain(session, recipient_paymail=user.paymail)

    # Store the NFT in the database.
    session.add(nft)
    session.flush()

    # Link the NFT to the user and optionally generate the triggered bingo card.
    nft.issue_dbwise_to(session, user)
    if create_new_bingo_card:
        BingoCard.generate_for_user(session, user, center_template=nft_template)

    session.flush()

    return nft


def update_user_bingo_info(session: Session, user: User) -> None:
    """Ensure the user's bingo cards reflect the NFTs currently assigned.

    The helper refreshes or creates bingo cards and their cells by delegating to
    ``User`` convenience methods, keeping both tables in sync with the user's
    holdings.
    """
    user.ensure_bingo_cards(session)
    user.ensure_bingo_cells(session)

    session.flush()
