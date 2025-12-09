from typing import TYPE_CHECKING, Iterable, Optional, Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PrizeDrawResult, PrizeDrawType, PrizeDrawWinningNumber
from .models.nft import NFT
from .models.user import User
from .prize_draw.engine import PrizeDrawEngine
from .prize_draw.scoring import AlgorithmRegistry

if TYPE_CHECKING:
    from .models import Admin, NFT, NFTTemplate
    from .blockchain.api import ChainClient


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
        from .blockchain.api import ChainClient

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
) -> PrizeDrawWinningNumber:
    """Persist a winning number for ``draw_type``.

    Parameters
    ----------
    session : Session
        Active SQLAlchemy session used for persistence.
    draw_type : PrizeDrawType
        Draw configuration that contains the winning number.
    value : str
        Literal winning number value recorded for auditing.

    Returns
    -------
    PrizeDrawWinningNumber
        Newly persisted ORM entity representing the winning number.
    """

    # Ensure the draw type is persisted.
    if draw_type.id is None:
        raise ValueError(
            "Draw type must be persisted before recording a winning number"
        )

    # Create and persist the winning number.
    winning_number = PrizeDrawWinningNumber(
        draw_type_id=draw_type.id,
        value=value,
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
    registry: Optional[AlgorithmRegistry] = None,
) -> PrizeDrawResult:
    """Evaluate a single NFT and persist the resulting ``PrizeDrawResult``.

    If ``winning_number`` is not provided, the latest winning number
    for ``draw_type`` will be used. If no winning number is available, the evaluation
    will be recorded with a "pending" outcome, allowing callers to
    "pre-register" the evaluation.

    This function essentially wraps :class:`PrizeDrawEngine`.

    Parameters
    ----------
    session : Session
        Active session used for persistence and queries.
    nft : NFT
        The NFT instance to evaluate.
    draw_type : PrizeDrawType
        Draw configuration that determines algorithm and thresholds.
    winning_number : Optional[PrizeDrawWinningNumber], default: None
        Winning number to use. When omitted, the most recently stored winning
        number is used automatically.
    threshold : Optional[float], default: None
        Optional threshold override applied to the evaluation.
    registry : Optional[AlgorithmRegistry], default: None
        Optional scoring registry containing custom scoring algorithms
        to be used instead of the engine default.

    Returns
    -------
    PrizeDrawResult
        Persisted row representing the latest evaluation outcome.

    Raises
    ------
    ValueError
        If the NFT or draw type prerequisites required by the engine are not met.
    """

    engine = PrizeDrawEngine(session, registry=registry)
    winning_number = winning_number or draw_type.latest_winning_number(session)

    evaluation = engine.evaluate(
        nft=nft,
        draw_type=draw_type,
        winning_number=winning_number,
        threshold=threshold,
        registry=registry,
    )
    session.flush()
    return evaluation.result


def _unique_nfts_preserve_insertion(nfts: Iterable["NFT"]) -> list["NFT"]:
    """Return unique NFTs while preserving the first-seen order."""

    unique: list[NFT] = []
    seen: set[int] = set()
    for nft in nfts:
        if nft.id is None:
            raise ValueError("NFT must be persisted before running a prize draw")
        if nft.id in seen:
            continue
        seen.add(nft.id)
        unique.append(nft)
    return unique


def _nfts_in_completed_bingo_lines(session: Session) -> list["NFT"]:
    """Return NFTs that belong to any completed bingo line."""

    from .models.bingo import BingoCard

    cards = session.scalars(select(BingoCard)).all()
    eligible: list[NFT] = []
    for card in cards:
        completed_lines = card.completed_lines
        if not completed_lines:
            continue

        cells_by_idx = {cell.idx: cell for cell in card.cells}
        for line in completed_lines:
            for idx in line:
                cell = cells_by_idx.get(idx)
                if cell is not None and cell.nft is not None:
                    eligible.append(cell.nft)

    return _unique_nfts_preserve_insertion(eligible)


def _nfts_for_template_with_ownership(
    session: Session,
    template_id: int,
) -> list["NFT"]:
    """Return NFTs minted from ``template_id`` that have an ownership record."""

    from .models.ownership import UserNFTOwnership

    stmt = (
        select(NFT)
        .join(UserNFTOwnership, UserNFTOwnership.nft_id == NFT.id)
        .where(NFT.template_id == template_id)
        .order_by(NFT.id.asc())
    )
    return _unique_nfts_preserve_insertion(session.scalars(stmt).all())


def _rank_prize_draw_results_with_ties(
    results: Sequence[PrizeDrawResult],
    *,
    limit: Optional[int] = None,
) -> list[PrizeDrawResult]:
    """Return results ranked by similarity, including any ties at the cutoff."""

    if limit is not None and limit < 0:
        raise ValueError("limit must be non-negative when provided")

    normalized: list[PrizeDrawResult] = []
    for res in results:
        if res.similarity_score is None:
            raise ValueError(
                "Cannot rank prize draw results without similarity scores. "
                "Ensure a winning number is supplied before ranking."
            )
        normalized.append(res)

    sorted_results = sorted(
        normalized,
        key=lambda res: (
            -float(res.similarity_score or 0.0),
            res.evaluated_at or datetime.min.replace(tzinfo=timezone.utc),
            res.id or 0,
        ),
    )

    if limit is None:
        return sorted_results
    if limit == 0:
        return []

    winners: list[PrizeDrawResult] = []
    cutoff_score: Optional[float] = None
    for res in sorted_results:
        score = res.similarity_score
        if score is None:
            continue
        if not winners or len(winners) < limit:
            winners.append(res)
            cutoff_score = score
            continue
        if cutoff_score is not None and score == cutoff_score:
            winners.append(res)
            continue
        break

    return winners


def run_prize_draw_batch(
    session: Session,
    draw_type: PrizeDrawType,
    *,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    nfts: Optional[Sequence[NFT]] = None,
    threshold: Optional[float] = None,
    registry: Optional[AlgorithmRegistry] = None,
) -> list[PrizeDrawResult]:
    """Evaluate multiple NFTs for ``draw_type`` and return their results.

    The helper is suitable for both ad-hoc reruns (``nfts`` is provided) and
    full-batch evaluations (``nfts`` omitted).  It always resolves a winning
    number before calling into the engine so that downstream logic does not have
    to duplicate the lookup behaviour.

    Parameters
    ----------
    session : Session
        Session used to query NFTs and persist results.
    draw_type : PrizeDrawType
        Draw configuration used for evaluation, which determines the algorithm
        and default threshold.
    winning_number : Optional[PrizeDrawWinningNumber], default: None
        Overriding winning number applied to all NFTs. If omitted, the latest stored
        winning number is resolved.
    nfts : Optional[Sequence[NFT]], default: None
        Optional subset of NFT instances to evaluate. When omitted, all eligible
        NFTs (i.e. those that are related to a completed bingo card) stored
        in the database are processed.
    threshold : Optional[float], default: None
        Optional threshold override applied to each evaluation.
    registry : Optional[AlgorithmRegistry], default: None
        Optional scoring registry override that contains custom scoring algorithms.

    Returns
    -------
    list[PrizeDrawResult]
        List of persisted results corresponding to the evaluated NFTs.

    Raises
    ------
    ValueError
        If the draw type is not persisted or no winning number can be found.
    """

    if draw_type.id is None:
        raise ValueError("Draw type must be persisted before evaluating draws")

    resolved_winning_number = winning_number or draw_type.latest_winning_number(session)
    if resolved_winning_number is None:
        raise ValueError("No winning number is available for the supplied draw type")

    if nfts is None:
        nfts_to_evaluate = _nfts_in_completed_bingo_lines(session)

    else:
        nfts_to_evaluate = list(nfts)
        if not nfts_to_evaluate:
            return []

    results: list[PrizeDrawResult] = []
    for nft in nfts_to_evaluate:
        result = run_prize_draw(
            session=session,
            nft=nft,
            draw_type=draw_type,
            winning_number=resolved_winning_number,
            threshold=threshold,
            registry=registry,
        )
        results.append(result)

    session.flush()
    return results


def run_bingo_prize_draw(
    session: Session,
    draw_type: PrizeDrawType,
    *,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    threshold: Optional[float] = None,
    registry: Optional[AlgorithmRegistry] = None,
    limit: Optional[int] = None,
) -> list[PrizeDrawResult]:
    """Run a draw across NFTs that belong to completed bingo lines.

    NFTs are gathered dynamically at draw time from any completed lines on bingo
    cards. Results are ranked by similarity, and any entries tied at the cutoff
    score are returned together.
    """

    eligible_nfts = _nfts_in_completed_bingo_lines(session)
    if not eligible_nfts:
        return []

    results = run_prize_draw_batch(
        session,
        draw_type,
        winning_number=winning_number,
        nfts=eligible_nfts,
        threshold=threshold,
        registry=registry,
    )
    return _rank_prize_draw_results_with_ties(results, limit=limit)


def run_final_attendance_prize_draw(
    session: Session,
    draw_type: PrizeDrawType,
    *,
    attendance_template_id: Optional[int] = None,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    threshold: Optional[float] = None,
    registry: Optional[AlgorithmRegistry] = None,
    limit: Optional[int] = None,
) -> list[PrizeDrawResult]:
    """Run a draw that targets only the final-day attendance stamp NFTs.

    ``attendance_template_id`` must be supplied to resolve the attendance
    template. Only NFTs minted from that template (and with at least one
    ownership record) participate in the draw.
    Winners are ranked by similarity with ties included at the cutoff.
    """

    if attendance_template_id is None:
        raise ValueError("attendance_template_id is required")

    eligible_nfts = _nfts_for_template_with_ownership(session, attendance_template_id)
    if not eligible_nfts:
        return []

    results = run_prize_draw_batch(
        session,
        draw_type,
        winning_number=winning_number,
        nfts=eligible_nfts,
        threshold=threshold,
        registry=registry,
    )
    return _rank_prize_draw_results_with_ties(results, limit=limit)


def select_top_prize_draw_results(
    session: Session,
    draw_type: PrizeDrawType,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    *,
    limit: int,
    include_pending: bool = True,
) -> list[PrizeDrawResult]:
    """Return up to `limit` PrizeDrawResult rows for the given draw type and
    winning number, ranked by similarity score (highest first).

    The helper is designed for "closest-number wins" scenarios where the
    highest similarity scores determine the winners. It filters results for the
    supplied draw type and winning number, orders them by ``similarity_score`` in
    descending order, and returns the top ``limit`` entries. Pending outcomes are
    included by default so that draws evaluated without thresholds remain
    eligible. Set ``include_pending`` to ``False`` to restrict the selection to
    non-pending outcomes.

    Parameters
    ----------
    session : Session
        Active SQLAlchemy session used to issue the query.
    draw_type : PrizeDrawType
        Persisted draw type whose results should be ranked.
    winning_number : Optional[PrizeDrawWinningNumber], default: None
        Winning number used to scope the results. When omitted, the latest
        persisted winning number for ``draw_type`` is resolved automatically.
    limit : int
        Maximum number of results to return. Must be greater than zero.
    include_pending : bool, default: True
        When ``True`` (default) pending outcomes are included in the ranking. Set
        to ``False`` to exclude them.

    Returns
    -------
    list[PrizeDrawResult]
        Top ``limit`` results ordered from highest to lowest similarity score.

    Raises
    ------
    ValueError
    If the draw type or winning number have not been persisted, if no
    winning number can be resolved, or if the requested ``limit`` is not
    positive.
    """

    if draw_type.id is None:
        raise ValueError("Draw type must be persisted before selecting results")
    if limit <= 0:
        raise ValueError("limit must be a positive integer")

    resolved_winning_number = winning_number or draw_type.latest_winning_number(session)

    if resolved_winning_number is None:
        raise ValueError("No winning number is available for the supplied draw type")
    if resolved_winning_number.id is None:
        raise ValueError("Winning number must be persisted before selecting results")

    stmt = select(PrizeDrawResult).where(
        PrizeDrawResult.draw_type_id == draw_type.id,
        PrizeDrawResult.winning_number_id == resolved_winning_number.id,
        PrizeDrawResult.similarity_score.isnot(None),
    )

    if not include_pending:
        stmt = stmt.where(PrizeDrawResult.outcome != "pending")

    stmt = stmt.order_by(
        PrizeDrawResult.similarity_score.desc().nulls_last(),
        PrizeDrawResult.evaluated_at.asc(),
        PrizeDrawResult.id.asc(),
    ).limit(limit)

    return list(session.scalars(stmt).all())
