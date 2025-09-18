from typing import TYPE_CHECKING, Optional
from sqlalchemy.orm import Session

from .models.user import User

if TYPE_CHECKING:
    from .models import Admin, NFT, NFTTemplate
    from nictbw.blockchain.api import ChainClient


def register_user(
    session: Session,
    user: User,
    password: str,
    email: str,
    username: Optional[str] = None,
    group: Optional[str] = None,
    profile_pic_filepath: Optional[str] = None,
    client: Optional["ChainClient"] = None,
) -> User:
    """Create a new user in the database and register them with the blockchain API.

    The workflow performs two coordinated tasks:

    1. Call the blockchain sign-up endpoint to register the wallet user and
       capture the generated paymail address.
    2. Persist the User record locally with the obtained paymail.

    The blockchain ``username`` defaults to the ``user.in_app_id`` when not
    explicitly provided.

    Parameters
    ----------
    session : Session
        Active SQLAlchemy session.
    user : User
        The User to be registered. Its ``paymail`` attribute will
        be overwritten with the value returned by the blockchain service.
    password : str
        User's password forwarded to the blockchain API.
    email : str
        User's email forwarded to the blockchain API.
    username : Optional[str]
        Optional blockchain username. When omitted ``user.in_app_id`` is used.
    group : Optional[str]
        Optional blockchain user group assigned during sign-up.
    profile_pic_filepath : Optional[str]
        Optional path to a profile picture uploaded during sign-up.
    client : Optional[ChainClient]
        Optional pre-configured :class:`~nictbw.blockchain.api.ChainClient`.
        If not provided, a default one will be created.

    Returns
    -------
    User
        The persisted ``User`` instance with populated ``id`` and ``paymail``.
    """
    from datetime import datetime, timezone

    if user.id is not None:
        raise ValueError("User already has an ID, cannot register again.")

    signup_username = username or user.in_app_id
    if not signup_username:
        raise ValueError("A blockchain username is required to register the user.")

    if client is None:
        from nictbw.blockchain.api import ChainClient

        client = ChainClient()

    # Call the blockchain sign-up endpoint
    response = client.signup_user(
        username=signup_username,
        email=email,
        password=password,
        profile_pic_filepath=profile_pic_filepath,
        group=group,
    )

    # Expect a dict response from the blockchain API
    if not isinstance(response, dict):
        raise RuntimeError(f"Unexpected blockchain sign-up response: {response!r}")

    status = response.get("status")
    if status != "success":
        message = response.get("message")
        raise RuntimeError(
            "Blockchain sign-up failed" + (f": {message}" if message else ".")
        )

    paymail = response.get("paymail")
    if not paymail:
        raise ValueError("Blockchain sign-up response did not include a paymail.")

    user.paymail = paymail
    user.on_chain_id = signup_username
    user.updated_at = datetime.now(timezone.utc)

    session.add(user)
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
