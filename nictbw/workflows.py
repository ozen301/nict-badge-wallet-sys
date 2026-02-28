from typing import TYPE_CHECKING, Iterable, Optional, Sequence
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import PrizeDrawResult, PrizeDrawType, PrizeDrawWinningNumber
from .models.nft import NFTDefinition
from .models.ownership import NFTInstance
from .models.user import User
from .prize_draw.engine import PrizeDrawEngine
from .prize_draw.scoring import AlgorithmRegistry

if TYPE_CHECKING:
    from .models import Admin, NFTTemplate
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
    if user.email is None:
        user.email = email
    user.on_chain_id = signup_username
    user.updated_at = datetime.now(timezone.utc)

    session.add(user)
    session.flush()

    return user


def create_and_issue_instance(
    session: Session,
    user: User,
    shared_key: Optional[str],
    definition_or_template: "NFTDefinition | NFTTemplate",
) -> "NFTInstance":
    """Create (if needed) and issue an NFT instance to a user.

    ``definition_or_template`` can be either an existing NFT definition or an NFTTemplate.
    When a template is supplied, a definition row is created/reused and then
    issued to ``user`` as an NFT instance.
    """
    from .models.bingo import BingoCard
    from .models.nft import NFTTemplate

    if isinstance(definition_or_template, NFTTemplate):
        if shared_key is None:
            raise ValueError("shared_key is required when instantiating from a template")
        instance = definition_or_template.instantiate_instance(
            session,
            user,
            shared_key=shared_key,
        )
    else:
        instance = definition_or_template.issue_dbwise_to_user(session, user)

    definition = instance.definition
    if definition.triggers_bingo_card:
        BingoCard.generate_for_user(session, user, definition)

    session.flush()
    return instance


def update_user_bingo_info(session: Session, user: User) -> None:
    """Ensure the user's bingo cards reflect the NFT instances currently assigned.

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
    instance: "NFTInstance",
    draw_type: PrizeDrawType,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    *,
    threshold: Optional[float] = None,
    registry: Optional[AlgorithmRegistry] = None,
) -> PrizeDrawResult:
    """Evaluate a single NFT instance and persist the resulting ``PrizeDrawResult``.

    If ``winning_number`` is not provided, the latest winning number
    for ``draw_type`` will be used. If no winning number is available, the evaluation
    will be recorded with a "pending" outcome, allowing callers to
    "pre-register" the evaluation.

    This function essentially wraps :class:`PrizeDrawEngine`.

    Parameters
    ----------
    session : Session
        Active session used for persistence and queries.
    instance : NFTInstance
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
        If the NFT instance or draw type prerequisites required by the engine are not met.
    """

    engine = PrizeDrawEngine(session, registry=registry)
    winning_number = winning_number or draw_type.latest_winning_number(session)

    evaluation = engine.evaluate(
        nft_instance=instance,
        draw_type=draw_type,
        winning_number=winning_number,
        threshold=threshold,
        registry=registry,
    )
    session.flush()
    return evaluation.result


def _unique_instances_preserve_insertion(
    instances: Iterable["NFTInstance"],
) -> list["NFTInstance"]:
    """Return unique NFT instances while preserving the first-seen order."""

    unique: list[NFTInstance] = []
    seen: set[int] = set()
    for instance in instances:
        if instance.id is None:
            raise ValueError("NFT instance must be persisted before running a prize draw")
        if instance.id in seen:
            continue
        seen.add(instance.id)
        unique.append(instance)
    return unique


def _validate_instances_compatible_with_result_uniqueness(
    instances: Sequence["NFTInstance"],
) -> None:
    """Validate instance batches against current prize-result uniqueness constraints."""

    first_instance_per_definition: dict[int, int] = {}
    for instance in instances:
        if instance.id is None:
            raise ValueError("NFT instance must be persisted before running a prize draw")
        if instance.definition_id is None:
            raise ValueError(
                "NFT instance must have a definition_id before running a prize draw"
            )

        prior_instance_id = first_instance_per_definition.get(instance.definition_id)
        if prior_instance_id is None:
            first_instance_per_definition[instance.definition_id] = instance.id
            continue

        if prior_instance_id != instance.id:
            raise ValueError(
                "Batch contains multiple NFT instances for the same NFT definition. "
                "Current schema uniqueness on (nft_id, draw_type_id) cannot store "
                "separate results per instance."
            )


def _instances_in_completed_bingo_lines(session: Session) -> list["NFTInstance"]:
    """Return NFT instances that belong to any completed bingo line."""

    from .models.bingo import BingoCard

    cards = session.scalars(select(BingoCard)).all()
    eligible: list[NFTInstance] = []
    for card in cards:
        completed_lines = card.completed_lines
        if not completed_lines:
            continue

        cells_by_idx = {cell.idx: cell for cell in card.cells}
        for line in completed_lines:
            for idx in line:
                cell = cells_by_idx.get(idx)
                if cell is not None and cell.matched_nft_instance is not None:
                    eligible.append(cell.matched_nft_instance)

    return _unique_instances_preserve_insertion(eligible)


def _instances_for_definition(
    session: Session,
    definition_id: int,
) -> list["NFTInstance"]:
    """Return instances for the supplied NFT definition id."""

    stmt = select(NFTInstance).where(NFTInstance.definition_id == definition_id).order_by(
        NFTInstance.id.asc()
    )
    return _unique_instances_preserve_insertion(session.scalars(stmt).all())


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
    instances: Optional[Sequence[NFTInstance]] = None,
    threshold: Optional[float] = None,
    registry: Optional[AlgorithmRegistry] = None,
) -> list[PrizeDrawResult]:
    """Evaluate multiple NFT instances for ``draw_type`` and return their results.

    The helper is suitable for both ad-hoc reruns (``instances`` is provided) and
    full-batch evaluations (``instances`` omitted). It always resolves a winning
    number before calling into the engine so that downstream logic does not have
    to duplicate the lookup behaviour.

    Parameters
    ----------
    session : Session
        Session used to query NFT instances and persist results.
    draw_type : PrizeDrawType
        Draw configuration used for evaluation, which determines the algorithm
        and default threshold.
    winning_number : Optional[PrizeDrawWinningNumber], default: None
        Overriding winning number applied to all instances. If omitted, the latest stored
        winning number is resolved.
    instances : Optional[Sequence[NFTInstance]], default: None
        Optional subset of NFT instances to evaluate. When omitted, all eligible
        instances on completed bingo lines are processed.
    threshold : Optional[float], default: None
        Optional threshold override applied to each evaluation.
    registry : Optional[AlgorithmRegistry], default: None
        Optional scoring registry override that contains custom scoring algorithms.

    Returns
    -------
    list[PrizeDrawResult]
        List of persisted results corresponding to the evaluated instances.

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

    if instances is None:
        instances_to_evaluate = _instances_in_completed_bingo_lines(session)

    else:
        instances_to_evaluate = list(instances)
        if not instances_to_evaluate:
            return []

    _validate_instances_compatible_with_result_uniqueness(instances_to_evaluate)

    results: list[PrizeDrawResult] = []
    for instance in instances_to_evaluate:
        result = run_prize_draw(
            session=session,
            instance=instance,
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
    """Run a draw across instances that belong to completed bingo lines.

    Instances are gathered dynamically at draw time from any completed lines on bingo
    cards. Results are ranked by similarity, and any entries tied at the cutoff
    score are returned together.
    """

    eligible_instances = _instances_in_completed_bingo_lines(session)
    if not eligible_instances:
        return []

    results = run_prize_draw_batch(
        session,
        draw_type,
        winning_number=winning_number,
        instances=eligible_instances,
        threshold=threshold,
        registry=registry,
    )
    return _rank_prize_draw_results_with_ties(results, limit=limit)


def run_final_attendance_prize_draw(
    session: Session,
    draw_type: PrizeDrawType,
    *,
    attendance_definition_id: Optional[int] = None,
    winning_number: Optional[PrizeDrawWinningNumber] = None,
    threshold: Optional[float] = None,
    registry: Optional[AlgorithmRegistry] = None,
    limit: Optional[int] = None,
) -> list[PrizeDrawResult]:
    """Run a draw that targets only the final-day attendance stamp instances.

    ``attendance_definition_id`` must be supplied to resolve the attendance
    NFT definition. Only instances for that definition participate in the draw.
    Winners are ranked by similarity with ties included at the cutoff.
    """

    if attendance_definition_id is None:
        raise ValueError("attendance_definition_id is required")

    eligible_instances = _instances_for_definition(
        session, attendance_definition_id
    )
    if not eligible_instances:
        return []

    results = run_prize_draw_batch(
        session,
        draw_type,
        winning_number=winning_number,
        instances=eligible_instances,
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
