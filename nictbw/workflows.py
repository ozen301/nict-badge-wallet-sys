from typing import TYPE_CHECKING, Any, Optional, Sequence
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PrizeDrawResult, PrizeDrawType, PrizeDrawWinningNumber
from .models.nft import NFT
from .models.user import User
from .prize_draw.engine import PrizeDrawEngine
from .prize_draw.scoring import AlgorithmRegistry

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


def submit_winning_number(
    session: Session,
    draw_type: PrizeDrawType,
    value: str,
    *,
    metadata: Optional[dict[str, Any] | str] = None,
    effective_at: Optional["datetime"] = None,
    expires_at: Optional["datetime"] = None,
) -> PrizeDrawWinningNumber:
    """Persist a winning number for ``draw_type`` and return the ORM entity.

    The `value` is a string that holds the winning number.
    """

    # Ensure the draw type is persisted.
    if draw_type.id is None:
        raise ValueError(
            "Draw type must be persisted before recording a winning number"
        )

    # Handle metadata serialization.
    if metadata is None:
        metadata_json = None
    elif isinstance(metadata, str):
        metadata_json = metadata
    else:
        import json

        metadata_json = json.dumps(metadata, sort_keys=True)

    # Create and persist the winning number.
    winning_number = PrizeDrawWinningNumber(
        draw_type_id=draw_type.id,
        value=value,
        metadata_json=metadata_json,
        effective_at=effective_at,
        expires_at=expires_at,
    )
    session.add(winning_number)
    session.flush()
    return winning_number


def run_prize_draw(
    session: Session,
    nft: "NFT",
    draw_type: PrizeDrawType,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    *,
    threshold: Optional[float] = None,
    algorithm_version: Optional[str] = None,
    payload: Optional[dict[str, Any] | str] = None,
    registry: Optional[AlgorithmRegistry] = None,
) -> PrizeDrawResult:
    """Evaluate ``nft`` once, persist the result, and return the stored :class:`PrizeDrawResult`.

    If ``winning_number`` is not provided, the latest effective winning number
    for ``draw_type`` will be used. If no winning number is available, the evaluation
    will be recorded with a `PrizeDrawOutcome.PENDING` outcome, allowing callers to
    "pre-register" the evaluation.
    
    This function essentially wraps :class:`PrizeDrawEngine`.
    """

    engine = PrizeDrawEngine(session, registry=registry)
    winning_number = winning_number or _latest_winning_number(session, draw_type)

    evaluation = engine.evaluate(
        nft=nft,
        draw_type=draw_type,
        winning_number=winning_number,
        threshold=threshold,
        algorithm_version=algorithm_version,
        payload=payload,
        registry=registry,
    )
    session.flush()
    return evaluation.result


def evaluate_draws(
    session: Session,
    draw_type: PrizeDrawType,
    *,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    nft_ids: Optional[Sequence[int]] = None,
    threshold: Optional[float] = None,
    algorithm_version: Optional[str] = None,
    payload: Optional[dict[str, Any] | str] = None,
    registry: Optional[AlgorithmRegistry] = None,
) -> list[PrizeDrawResult]:
    """Evaluate multiple NFTs for ``draw_type`` and return their results.

    The helper is suitable for both ad-hoc reruns (``nft_ids`` is provided) and
    full-batch evaluations (``nft_ids`` omitted).  It always resolves a winning
    number before calling into the engine so that downstream logic does not have
    to duplicate the lookup behaviour.
    """

    if draw_type.id is None:
        raise ValueError("Draw type must be persisted before evaluating draws")

    resolved_winning_number = winning_number or _latest_winning_number(
        session, draw_type
    )
    if resolved_winning_number is None:
        raise ValueError("No winning number is available for the supplied draw type")

    engine = PrizeDrawEngine(session, registry=registry)

    stmt = select(NFT)
    if nft_ids is not None:
        if not nft_ids:
            return []
        # SQLAlchemy cannot bind empty ``IN`` clauses, therefore the explicit
        # guard and early return above.  ``list`` is used to support iterables
        # such as tuples or generators.
        stmt = stmt.where(NFT.id.in_(list(nft_ids)))

    nfts = list(session.scalars(stmt))
    results: list[PrizeDrawResult] = []
    for nft in nfts:
        evaluation = engine.evaluate(
            nft=nft,
            draw_type=draw_type,
            winning_number=resolved_winning_number,
            threshold=threshold,
            algorithm_version=algorithm_version,
            payload=payload,
            registry=registry,
        )
        results.append(evaluation.result)

    session.flush()
    return results


def _latest_winning_number(
    session: Session, draw_type: PrizeDrawType
) -> Optional[PrizeDrawWinningNumber]:
    """Return the most recently effective winning number for ``draw_type``."""

    # Order by effective window first so that future-dated winning numbers are
    # naturally considered "latest" once their window starts.  ``nullslast``
    # keeps permanently active numbers at the end of the ordering for clarity.
    stmt = (
        select(PrizeDrawWinningNumber)
        .where(PrizeDrawWinningNumber.draw_type_id == draw_type.id)
        .order_by(
            PrizeDrawWinningNumber.effective_at.desc().nullslast(),
            PrizeDrawWinningNumber.created_at.desc(),
            PrizeDrawWinningNumber.id.desc(),
        )
    )
    return session.scalars(stmt).first()
