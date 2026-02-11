from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Delegation,
    Document,
    EscalationState,
    Notification,
    ReviewCycle,
    ReviewDecision,
    ReviewerAssignment,
)


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        meta: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.meta = meta or {}


def _now() -> datetime:
    return datetime.utcnow()


def _to_naive_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _new_id() -> str:
    return str(uuid.uuid4())


def create_document(
    session: Session, title: str, content: str, author_id: str
) -> Document:
    document = Document(
        id=_new_id(),
        title=title,
        content=content,
        author_id=author_id,
        status="draft",
        created_at=_now(),
        updated_at=_now(),
    )
    session.add(document)
    session.flush()
    return document


def _get_document(session: Session, document_id: str) -> Document:
    document = session.get(Document, document_id)
    if not document:
        raise ApiError(404, "document_not_found", "Document not found")
    return document


def _get_active_cycle(session: Session, document_id: str) -> ReviewCycle | None:
    statement = (
        select(ReviewCycle)
        .where(ReviewCycle.document_id == document_id)
        .order_by(ReviewCycle.cycle_index.desc())
    )
    return session.execute(statement).scalars().first()


def _list_assignments(session: Session, cycle_id: int) -> list[ReviewerAssignment]:
    statement = select(ReviewerAssignment).where(
        ReviewerAssignment.cycle_id == cycle_id
    )
    return list(session.execute(statement).scalars().all())


def _list_decisions(session: Session, cycle_id: int) -> list[ReviewDecision]:
    statement = select(ReviewDecision).where(ReviewDecision.cycle_id == cycle_id)
    return list(session.execute(statement).scalars().all())


def update_document(
    session: Session,
    document_id: str,
    editor_id: str,
    title: str,
    content: str,
) -> Document:
    document = _get_document(session, document_id)
    if document.status == "approved":
        raise ApiError(409, "document_locked", "Document is locked")
    if document.status == "review":
        raise ApiError(409, "document_under_review", "Document is under review")
    document.title = title
    document.content = content
    document.updated_at = _now()
    session.add(document)
    return document


def submit_document(
    session: Session,
    document_id: str,
    author_id: str,
    reviewer_ids: list[str],
    escalation: dict[str, Any] | None,
) -> ReviewCycle:
    document = _get_document(session, document_id)
    if document.author_id != author_id:
        raise ApiError(403, "not_author", "Only the author can submit the document")
    if not reviewer_ids:
        raise ApiError(400, "reviewers_required", "At least one reviewer is required")
    if document.status not in {"draft", "rejected"}:
        raise ApiError(
            409,
            "invalid_transition",
            "Document cannot be submitted in its current state",
        )

    previous_cycle = _get_active_cycle(session, document_id)
    cycle_index = 1 if not previous_cycle else previous_cycle.cycle_index + 1
    cycle = ReviewCycle(
        document_id=document.id,
        cycle_index=cycle_index,
        status="review",
        created_at=_now(),
    )
    session.add(cycle)
    session.flush()

    for reviewer_id in reviewer_ids:
        assignment = ReviewerAssignment(
            cycle_id=cycle.id, reviewer_id=reviewer_id, active=True
        )
        session.add(assignment)

    if escalation:
        timeout_hours = int(escalation.get("timeout_hours", 0))
        ladder = escalation.get("ladder", [])
        start_at_raw = escalation.get("start_at")
        start_at = _now()
        if start_at_raw:
            if isinstance(start_at_raw, str):
                normalized = start_at_raw.replace("Z", "+00:00")
                start_at = datetime.fromisoformat(normalized)
            elif isinstance(start_at_raw, datetime):
                start_at = start_at_raw
        start_at = _to_naive_utc(start_at)
        next_escalation_at = (
            start_at + timedelta(hours=timeout_hours) if timeout_hours else None
        )
        escalation_state = EscalationState(
            cycle_id=cycle.id,
            timeout_hours=timeout_hours,
            ladder_json=json.dumps(ladder),
            current_index=0,
            next_escalation_at=next_escalation_at,
            last_escalated_at=None,
        )
        session.add(escalation_state)

    document.status = "review"
    document.updated_at = _now()
    session.add(document)
    session.flush()

    for reviewer_id in reviewer_ids:
        notification = Notification(
            id=_new_id(),
            document_id=document.id,
            recipient_id=reviewer_id,
            message="Document submitted for review",
            created_at=_now(),
        )
        session.add(notification)

    return cycle


def _ensure_reviewer_assignment(
    assignments: list[ReviewerAssignment], reviewer_id: str
) -> None:
    if reviewer_id not in {assignment.reviewer_id for assignment in assignments}:
        raise ApiError(
            403, "reviewer_not_assigned", "Reviewer is not assigned to this document"
        )


def _ensure_no_decision(decisions: list[ReviewDecision], reviewer_id: str) -> None:
    if reviewer_id in {decision.reviewer_id for decision in decisions}:
        raise ApiError(
            409, "review_decision_exists", "Reviewer has already submitted a decision"
        )


def _ensure_not_author(document: Document, reviewer_id: str) -> None:
    if reviewer_id == document.author_id:
        raise ApiError(403, "self_approval_forbidden", "Self approval is not permitted")


@dataclass
class DelegationContext:
    delegator_id: str
    acted_by: str


def _resolve_actor(
    session: Session,
    cycle_id: int,
    actor_id: str,
    on_behalf_of: str | None,
    now: datetime,
) -> DelegationContext:
    now = _to_naive_utc(now)
    if not on_behalf_of:
        return DelegationContext(delegator_id=actor_id, acted_by=actor_id)

    delegation = (
        session.execute(
            select(Delegation)
            .where(Delegation.cycle_id == cycle_id)
            .where(Delegation.delegator_id == on_behalf_of)
            .where(Delegation.substitute_id == actor_id)
        )
        .scalars()
        .first()
    )
    if not delegation:
        raise ApiError(
            403, "delegation_missing", "Delegation does not exist for this document"
        )
    if delegation.revoked_at is not None:
        raise ApiError(403, "delegation_inactive", "Delegation has been revoked")
    if _to_naive_utc(delegation.expires_at) <= now:
        raise ApiError(403, "delegation_expired", "Delegation has expired")
    chain_check = (
        session.execute(
            select(Delegation)
            .where(Delegation.cycle_id == cycle_id)
            .where(Delegation.substitute_id == on_behalf_of)
            .where(Delegation.revoked_at.is_(None))
            .where(Delegation.expires_at > now)
        )
        .scalars()
        .first()
    )
    if chain_check:
        raise ApiError(
            403, "delegation_chain_forbidden", "Re-delegation is not permitted"
        )
    return DelegationContext(delegator_id=on_behalf_of, acted_by=actor_id)


def approve_document(
    session: Session,
    document_id: str,
    actor_id: str,
    on_behalf_of: str | None,
) -> ReviewDecision:
    document = _get_document(session, document_id)
    cycle = _get_active_cycle(session, document_id)
    if not cycle:
        raise ApiError(409, "invalid_transition", "Document is not under review")

    assignments = _list_assignments(session, cycle.id)
    decisions = _list_decisions(session, cycle.id)

    context = _resolve_actor(session, cycle.id, actor_id, on_behalf_of, _now())

    _ensure_reviewer_assignment(assignments, context.delegator_id)
    _ensure_no_decision(decisions, context.delegator_id)
    if document.status != "review":
        raise ApiError(409, "invalid_transition", "Document is not under review")
    _ensure_not_author(document, context.delegator_id)

    decision = ReviewDecision(
        cycle_id=cycle.id,
        reviewer_id=context.delegator_id,
        status="approved",
        reason=None,
        acted_by=context.acted_by,
        decided_at=_now(),
    )
    session.add(decision)
    session.flush()

    _evaluate_cycle(session, document, cycle)
    return decision


def reject_document(
    session: Session,
    document_id: str,
    actor_id: str,
    reason: str,
    on_behalf_of: str | None,
) -> ReviewDecision:
    document = _get_document(session, document_id)
    cycle = _get_active_cycle(session, document_id)
    if not cycle:
        raise ApiError(409, "invalid_transition", "Document is not under review")

    assignments = _list_assignments(session, cycle.id)
    decisions = _list_decisions(session, cycle.id)

    context = _resolve_actor(session, cycle.id, actor_id, on_behalf_of, _now())

    _ensure_reviewer_assignment(assignments, context.delegator_id)
    _ensure_no_decision(decisions, context.delegator_id)
    if document.status != "review":
        raise ApiError(409, "invalid_transition", "Document is not under review")
    _ensure_not_author(document, context.delegator_id)

    decision = ReviewDecision(
        cycle_id=cycle.id,
        reviewer_id=context.delegator_id,
        status="rejected",
        reason=reason,
        acted_by=context.acted_by,
        decided_at=_now(),
    )
    session.add(decision)
    session.flush()

    cycle.status = "rejected"
    document.status = "rejected"
    document.updated_at = _now()
    session.add(cycle)
    session.add(document)
    return decision


def _evaluate_cycle(session: Session, document: Document, cycle: ReviewCycle) -> None:
    decisions = _list_decisions(session, cycle.id)
    assignments = _list_assignments(session, cycle.id)
    if any(decision.status == "rejected" for decision in decisions):
        cycle.status = "rejected"
        document.status = "rejected"
        document.updated_at = _now()
        session.add(cycle)
        session.add(document)
        return

    assigned_ids = {assignment.reviewer_id for assignment in assignments}
    decided_ids = {decision.reviewer_id for decision in decisions}
    if assigned_ids.issubset(decided_ids):
        cycle.status = "approved"
        document.status = "approved"
        document.updated_at = _now()
        session.add(cycle)
        session.add(document)
    else:
        cycle.status = "review"
        session.add(cycle)


def list_pending_reviewers(session: Session, cycle_id: int) -> list[str]:
    cycle = session.get(ReviewCycle, cycle_id)
    if not cycle or cycle.status != "review":
        return []
    assignments = _list_assignments(session, cycle_id)
    decisions = _list_decisions(session, cycle_id)
    decided_ids = {decision.reviewer_id for decision in decisions}
    return [
        assignment.reviewer_id
        for assignment in assignments
        if assignment.reviewer_id not in decided_ids
    ]


def list_reviewer_ids(session: Session, cycle_id: int) -> list[str]:
    assignments = _list_assignments(session, cycle_id)
    return [assignment.reviewer_id for assignment in assignments]


def list_review_history(session: Session, cycle_id: int) -> list[ReviewDecision]:
    return _list_decisions(session, cycle_id)


def list_review_history_for_document(
    session: Session, document_id: str
) -> list[ReviewDecision]:
    statement = (
        select(ReviewDecision)
        .join(ReviewCycle, ReviewDecision.cycle_id == ReviewCycle.id)
        .where(ReviewCycle.document_id == document_id)
    )
    return list(session.execute(statement).scalars().all())


def create_delegation(
    session: Session,
    document_id: str,
    delegator_id: str,
    substitute_id: str,
    expires_at: datetime,
) -> Delegation:
    document = _get_document(session, document_id)
    cycle = _get_active_cycle(session, document_id)
    if not cycle or document.status != "review":
        raise ApiError(409, "invalid_transition", "Document is not under review")

    chain_check = (
        session.execute(
            select(Delegation)
            .where(Delegation.cycle_id == cycle.id)
            .where(Delegation.substitute_id == delegator_id)
            .where(Delegation.revoked_at.is_(None))
            .where(Delegation.expires_at > _now())
        )
        .scalars()
        .first()
    )
    if chain_check:
        raise ApiError(
            403,
            "delegation_chain_forbidden",
            "Re-delegation is not permitted",
        )

    assignments = _list_assignments(session, cycle.id)
    _ensure_reviewer_assignment(assignments, delegator_id)

    existing = (
        session.execute(
            select(Delegation)
            .where(Delegation.cycle_id == cycle.id)
            .where(Delegation.delegator_id == delegator_id)
        )
        .scalars()
        .first()
    )
    if (
        existing
        and existing.revoked_at is None
        and _to_naive_utc(existing.expires_at) > _now()
    ):
        raise ApiError(
            409, "delegation_exists", "Delegation already exists for this reviewer"
        )

    delegation = Delegation(
        id=_new_id(),
        cycle_id=cycle.id,
        delegator_id=delegator_id,
        substitute_id=substitute_id,
        expires_at=expires_at,
        revoked_at=None,
        created_at=_now(),
    )
    session.add(delegation)
    return delegation


def revoke_delegation(
    session: Session,
    document_id: str,
    delegation_id: str,
    delegator_id: str,
) -> Delegation:
    document = _get_document(session, document_id)
    cycle = _get_active_cycle(session, document_id)
    if not cycle or document.status != "review":
        raise ApiError(409, "invalid_transition", "Document is not under review")
    delegation = session.get(Delegation, delegation_id)
    if not delegation or delegation.cycle_id != cycle.id:
        raise ApiError(404, "delegation_not_found", "Delegation not found")
    if delegation.delegator_id != delegator_id:
        raise ApiError(
            403, "delegation_forbidden", "Only the delegator can revoke delegation"
        )
    delegation.revoked_at = _now()
    session.add(delegation)
    return delegation


def list_notifications(session: Session, document_id: str) -> list[Notification]:
    statement = select(Notification).where(Notification.document_id == document_id)
    return list(session.execute(statement).scalars().all())


def trigger_escalation(
    session: Session, document_id: str, now: datetime
) -> EscalationState:
    now = _to_naive_utc(now)
    document = _get_document(session, document_id)
    cycle = _get_active_cycle(session, document_id)
    if not cycle or document.status != "review":
        raise ApiError(409, "escalation_not_applicable", "Escalation is not applicable")
    state = cycle.escalation_state
    if not state:
        raise ApiError(409, "escalation_not_applicable", "Escalation is not configured")
    next_escalation_at = (
        _to_naive_utc(state.next_escalation_at) if state.next_escalation_at else None
    )
    if not next_escalation_at or now < next_escalation_at:
        raise ApiError(
            409,
            "escalation_not_due",
            "Escalation timeout has not elapsed",
            meta={
                "next_escalation_at": next_escalation_at.isoformat()
                if next_escalation_at
                else None
            },
        )

    ladder = json.loads(state.ladder_json or "[]")
    if state.current_index >= len(ladder):
        raise ApiError(409, "escalation_max_depth", "Maximum escalation depth reached")
    escalated_to = ladder[state.current_index]

    existing_assignment = (
        session.execute(
            select(ReviewerAssignment)
            .where(ReviewerAssignment.cycle_id == cycle.id)
            .where(ReviewerAssignment.reviewer_id == escalated_to)
        )
        .scalars()
        .first()
    )
    if not existing_assignment:
        session.add(
            ReviewerAssignment(cycle_id=cycle.id, reviewer_id=escalated_to, active=True)
        )

    notification = Notification(
        id=_new_id(),
        document_id=document.id,
        recipient_id=escalated_to,
        message="Document escalated for review",
        created_at=_now(),
    )
    session.add(notification)

    state.last_escalated_at = now
    state.current_index += 1
    state.next_escalation_at = now + timedelta(hours=state.timeout_hours)
    session.add(state)
    return state
