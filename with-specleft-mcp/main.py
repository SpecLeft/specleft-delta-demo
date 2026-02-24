from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    create_engine,
    select,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)
from sqlalchemy.pool import StaticPool

DATABASE_URL = "sqlite:///./workflow.db"


def create_engine_from_url(database_url: str):
    if database_url.startswith("sqlite") and ":memory:" in database_url:
        return create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
    if database_url.startswith("sqlite"):
        return create_engine(database_url, connect_args={"check_same_thread": False})
    return create_engine(database_url)


engine = create_engine_from_url(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)


class ReviewCycle(Base):
    __tablename__ = "review_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    document: Mapped["Document"] = relationship(back_populates="review_cycles")
    reviewers: Mapped[List["DocumentReviewer"]] = relationship(
        back_populates="review_cycle", cascade="all, delete-orphan"
    )
    escalations: Mapped[List["EscalationEvent"]] = relationship(
        back_populates="review_cycle", cascade="all, delete-orphan"
    )


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft")
    author_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    reviewer_ids_text: Mapped[str] = mapped_column(Text, default="")
    current_cycle_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    escalation_timeout_seconds: Mapped[int] = mapped_column(Integer, default=86400)
    max_escalation_depth: Mapped[int] = mapped_column(Integer, default=3)
    escalation_chain_text: Mapped[str] = mapped_column(Text, default="")
    escalation_index: Mapped[int] = mapped_column(Integer, default=0)
    next_escalation_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime, nullable=True
    )

    author: Mapped[User] = relationship()
    review_cycles: Mapped[List[ReviewCycle]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    reviewers: Mapped[List["DocumentReviewer"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )
    delegations: Mapped[List["Delegation"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )


class DocumentReviewer(Base):
    __tablename__ = "document_reviewers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    review_cycle_id: Mapped[int] = mapped_column(ForeignKey("review_cycles.id"))
    reviewer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))

    assigned_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    decision: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    decision_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decision_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    decided_by_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True
    )

    document: Mapped[Document] = relationship(back_populates="reviewers")
    review_cycle: Mapped[ReviewCycle] = relationship(back_populates="reviewers")
    reviewer: Mapped[User] = relationship(foreign_keys=[reviewer_id])
    decided_by: Mapped[Optional[User]] = relationship(foreign_keys=[decided_by_id])


class Delegation(Base):
    __tablename__ = "delegations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    delegator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    substitute_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    document: Mapped[Document] = relationship(back_populates="delegations")
    delegator: Mapped[User] = relationship(foreign_keys=[delegator_id])
    substitute: Mapped[User] = relationship(foreign_keys=[substitute_id])


class EscalationEvent(Base):
    __tablename__ = "escalations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    review_cycle_id: Mapped[int] = mapped_column(ForeignKey("review_cycles.id"))
    escalated_to_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    depth: Mapped[int] = mapped_column(Integer, default=1)
    escalated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    review_cycle: Mapped[ReviewCycle] = relationship(back_populates="escalations")


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    document_id: Mapped[int] = mapped_column(ForeignKey("documents.id"))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UserCreate(BaseModel):
    name: str = Field(min_length=1)


class UserResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class DocumentCreate(BaseModel):
    author_id: int
    title: str = Field(min_length=1)
    content: str = ""
    reviewer_ids: List[int] = Field(default_factory=list)
    escalation_chain: List[int] = Field(default_factory=list)
    escalation_timeout_seconds: int = 86400
    max_escalation_depth: int = 3


class DocumentUpdate(BaseModel):
    author_id: int
    title: Optional[str] = None
    content: Optional[str] = None


class DocumentSubmit(BaseModel):
    author_id: int


class DocumentResubmit(BaseModel):
    author_id: int
    reviewer_ids: Optional[List[int]] = None


class ReviewDecision(BaseModel):
    actor_id: int
    decision: str
    reason: Optional[str] = None


class DelegateRequest(BaseModel):
    delegator_id: int
    substitute_id: int
    expires_at: datetime


class RevokeDelegationRequest(BaseModel):
    delegator_id: int


class EscalateRequest(BaseModel):
    triggered_by: Optional[str] = None


class ReviewerStatus(BaseModel):
    reviewer_id: int
    decision: Optional[str]
    decided_by_id: Optional[int]
    decision_at: Optional[datetime]
    decision_reason: Optional[str]


class EscalationStatus(BaseModel):
    escalated_to_id: int
    depth: int
    escalated_at: datetime


class ReviewCycleStatus(BaseModel):
    id: int
    created_at: datetime
    reviewers: List[ReviewerStatus]
    escalations: List[EscalationStatus]


class DocumentResponse(BaseModel):
    id: int
    title: str
    content: str
    status: str
    author_id: int
    reviewer_ids: List[int]
    pending_reviewer_ids: List[int]
    current_cycle_id: Optional[int]
    review_cycles: List[ReviewCycleStatus]

    class Config:
        from_attributes = True


class NotificationResponse(BaseModel):
    id: int
    user_id: int
    document_id: int
    message: str
    created_at: datetime

    class Config:
        from_attributes = True


def parse_ids(text: str) -> List[int]:
    if not text:
        return []
    return [int(value) for value in text.split(",") if value.strip()]


def ids_to_text(values: List[int]) -> str:
    return ",".join(str(value) for value in values)


def now_utc() -> datetime:
    return datetime.utcnow()


def configure_engine(database_url: str) -> None:
    global engine, SessionLocal
    engine = create_engine_from_url(database_url)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def get_document(session: Session, document_id: int) -> Document:
    document = session.get(Document, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="document not found")
    return document


def ensure_user(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return user


def ensure_review_cycle(document: Document, session: Session) -> ReviewCycle:
    if document.current_cycle_id is None:
        cycle = ReviewCycle(document=document)
        session.add(cycle)
        session.flush()
        document.current_cycle_id = cycle.id
        return cycle
    cycle = session.get(ReviewCycle, document.current_cycle_id)
    if not cycle:
        cycle = ReviewCycle(document=document)
        session.add(cycle)
        session.flush()
        document.current_cycle_id = cycle.id
    return cycle


def create_reviewer_assignments(
    session: Session, document: Document, cycle: ReviewCycle
) -> None:
    reviewer_ids = parse_ids(document.reviewer_ids_text)
    if not reviewer_ids:
        raise HTTPException(status_code=400, detail="at least one reviewer is required")
    existing = (
        session.execute(
            select(DocumentReviewer).where(
                DocumentReviewer.document_id == document.id,
                DocumentReviewer.review_cycle_id == cycle.id,
            )
        )
        .scalars()
        .all()
    )
    if existing:
        return
    for reviewer_id in reviewer_ids:
        ensure_user(session, reviewer_id)
        session.add(
            DocumentReviewer(
                document=document,
                review_cycle=cycle,
                reviewer_id=reviewer_id,
            )
        )


def create_notification(
    session: Session, user_id: int, document_id: int, message: str
) -> None:
    session.add(Notification(user_id=user_id, document_id=document_id, message=message))


def build_document_response(session: Session, document: Document) -> DocumentResponse:
    reviewer_ids = parse_ids(document.reviewer_ids_text)
    reviewer_ids = list(dict.fromkeys(reviewer_ids))
    pending_reviewer_ids: List[int] = []
    current_cycle_id = document.current_cycle_id
    review_cycles_data: List[ReviewCycleStatus] = []

    for cycle in document.review_cycles:
        reviewers = (
            session.execute(
                select(DocumentReviewer).where(
                    DocumentReviewer.review_cycle_id == cycle.id
                )
            )
            .scalars()
            .all()
        )
        escalations = (
            session.execute(
                select(EscalationEvent).where(
                    EscalationEvent.review_cycle_id == cycle.id
                )
            )
            .scalars()
            .all()
        )
        if cycle.id == current_cycle_id:
            for reviewer in reviewers:
                if reviewer.reviewer_id not in reviewer_ids:
                    reviewer_ids.append(reviewer.reviewer_id)
        if cycle.id == current_cycle_id:
            pending_reviewer_ids = [
                reviewer.reviewer_id
                for reviewer in reviewers
                if reviewer.decision is None
            ]
            escalated_ids = {event.escalated_to_id for event in escalations}
            for escalated_id in escalated_ids:
                if escalated_id not in reviewer_ids:
                    reviewer_ids.append(escalated_id)
        reviewer_statuses = [
            ReviewerStatus(
                reviewer_id=reviewer.reviewer_id,
                decision=reviewer.decision,
                decided_by_id=reviewer.decided_by_id,
                decision_at=reviewer.decision_at,
                decision_reason=reviewer.decision_reason,
            )
            for reviewer in reviewers
        ]
        escalation_statuses = [
            EscalationStatus(
                escalated_to_id=event.escalated_to_id,
                depth=event.depth,
                escalated_at=event.escalated_at,
            )
            for event in escalations
        ]
        review_cycles_data.append(
            ReviewCycleStatus(
                id=cycle.id,
                created_at=cycle.created_at,
                reviewers=reviewer_statuses,
                escalations=escalation_statuses,
            )
        )

    return DocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        status=document.status,
        author_id=document.author_id,
        reviewer_ids=reviewer_ids,
        pending_reviewer_ids=pending_reviewer_ids,
        current_cycle_id=current_cycle_id,
        review_cycles=review_cycles_data,
    )


def get_active_delegation(
    session: Session, document_id: int, delegator_id: int, substitute_id: int
) -> Optional[Delegation]:
    now = now_utc()
    delegation = (
        session.execute(
            select(Delegation).where(
                Delegation.document_id == document_id,
                Delegation.delegator_id == delegator_id,
                Delegation.substitute_id == substitute_id,
                Delegation.revoked_at.is_(None),
            )
        )
        .scalars()
        .first()
    )
    if not delegation:
        return None
    if delegation.expires_at <= now:
        return None
    return delegation


def decision_allowed(decision: str) -> bool:
    return decision in {"approve", "reject"}


def update_document_status(session: Session, document: Document) -> None:
    if document.current_cycle_id is None:
        return
    reviewers = (
        session.execute(
            select(DocumentReviewer).where(
                DocumentReviewer.review_cycle_id == document.current_cycle_id
            )
        )
        .scalars()
        .all()
    )
    if any(reviewer.decision == "reject" for reviewer in reviewers):
        document.status = "rejected"
        return
    if reviewers and all(reviewer.decision == "approve" for reviewer in reviewers):
        document.status = "approved"


app = FastAPI(title="Document Approval Workflow")


@app.on_event("startup")
def startup() -> None:
    init_db()


@app.post("/users", response_model=UserResponse)
def create_user(payload: UserCreate) -> UserResponse:
    with SessionLocal() as session:
        user = User(name=payload.name)
        session.add(user)
        session.commit()
        session.refresh(user)
        return UserResponse.model_validate(user)


@app.post("/documents", response_model=DocumentResponse)
def create_document(payload: DocumentCreate) -> DocumentResponse:
    with SessionLocal.begin() as session:
        ensure_user(session, payload.author_id)
        for reviewer_id in payload.reviewer_ids:
            ensure_user(session, reviewer_id)
        for escalated_id in payload.escalation_chain:
            ensure_user(session, escalated_id)
        document = Document(
            title=payload.title,
            content=payload.content,
            status="draft",
            author_id=payload.author_id,
            reviewer_ids_text=ids_to_text(payload.reviewer_ids),
            escalation_chain_text=ids_to_text(payload.escalation_chain),
            escalation_timeout_seconds=payload.escalation_timeout_seconds,
            max_escalation_depth=payload.max_escalation_depth,
        )
        session.add(document)
        session.flush()
        return build_document_response(session, document)


@app.get("/documents/{document_id}", response_model=DocumentResponse)
def get_document_status(document_id: int) -> DocumentResponse:
    with SessionLocal() as session:
        document = get_document(session, document_id)
        return build_document_response(session, document)


@app.patch("/documents/{document_id}", response_model=DocumentResponse)
def update_document(document_id: int, payload: DocumentUpdate) -> DocumentResponse:
    with SessionLocal.begin() as session:
        document = get_document(session, document_id)
        if document.author_id != payload.author_id:
            raise HTTPException(status_code=403, detail="only the author can edit")
        if document.status == "approved":
            raise HTTPException(status_code=400, detail="document is locked")
        if document.status == "review":
            raise HTTPException(status_code=400, detail="document is under review")
        if payload.title is not None:
            document.title = payload.title
        if payload.content is not None:
            document.content = payload.content
        document.updated_at = now_utc()
        return build_document_response(session, document)


@app.post("/documents/{document_id}/submit", response_model=DocumentResponse)
def submit_document(document_id: int, payload: DocumentSubmit) -> DocumentResponse:
    with SessionLocal.begin() as session:
        document = get_document(session, document_id)
        if document.author_id != payload.author_id:
            raise HTTPException(status_code=403, detail="only the author can submit")
        if document.status not in {"draft", "rejected"}:
            raise HTTPException(status_code=400, detail="invalid state transition")
        cycle = ReviewCycle(document=document)
        session.add(cycle)
        session.flush()
        document.current_cycle_id = cycle.id
        create_reviewer_assignments(session, document, cycle)
        document.status = "review"
        document.next_escalation_at = now_utc() + timedelta(
            seconds=document.escalation_timeout_seconds
        )
        document.escalation_index = 0
        reviewer_ids = parse_ids(document.reviewer_ids_text)
        for reviewer_id in reviewer_ids:
            create_notification(
                session,
                reviewer_id,
                document.id,
                "document submitted for review",
            )
        return build_document_response(session, document)


@app.post("/documents/{document_id}/resubmit", response_model=DocumentResponse)
def resubmit_document(document_id: int, payload: DocumentResubmit) -> DocumentResponse:
    with SessionLocal.begin() as session:
        document = get_document(session, document_id)
        if document.author_id != payload.author_id:
            raise HTTPException(status_code=403, detail="only the author can resubmit")
        if document.status != "rejected":
            raise HTTPException(
                status_code=400, detail="only rejected documents can resubmit"
            )
        if payload.reviewer_ids is not None:
            for reviewer_id in payload.reviewer_ids:
                ensure_user(session, reviewer_id)
            document.reviewer_ids_text = ids_to_text(payload.reviewer_ids)
        cycle = ReviewCycle(document=document)
        session.add(cycle)
        session.flush()
        document.current_cycle_id = cycle.id
        create_reviewer_assignments(session, document, cycle)
        document.status = "review"
        document.next_escalation_at = now_utc() + timedelta(
            seconds=document.escalation_timeout_seconds
        )
        document.escalation_index = 0
        reviewer_ids = parse_ids(document.reviewer_ids_text)
        for reviewer_id in reviewer_ids:
            create_notification(
                session,
                reviewer_id,
                document.id,
                "document resubmitted for review",
            )
        return build_document_response(session, document)


@app.post("/documents/{document_id}/review", response_model=DocumentResponse)
def review_document(document_id: int, payload: ReviewDecision) -> DocumentResponse:
    with SessionLocal.begin() as session:
        document = get_document(session, document_id)
        actor = ensure_user(session, payload.actor_id)
        if not decision_allowed(payload.decision):
            raise HTTPException(status_code=400, detail="invalid decision")

        cycle_id = document.current_cycle_id
        if cycle_id is None:
            raise HTTPException(status_code=400, detail="review cycle not initialized")

        assignment = (
            session.execute(
                select(DocumentReviewer).where(
                    DocumentReviewer.review_cycle_id == cycle_id,
                    DocumentReviewer.reviewer_id == actor.id,
                )
            )
            .scalars()
            .first()
        )

        delegator_id = None
        if assignment is None:
            delegation = (
                session.execute(
                    select(Delegation).where(
                        Delegation.document_id == document.id,
                        Delegation.substitute_id == actor.id,
                        Delegation.revoked_at.is_(None),
                    )
                )
                .scalars()
                .first()
            )
            if delegation and delegation.expires_at <= now_utc():
                raise HTTPException(status_code=400, detail="delegation has expired")
            if delegation:
                delegator_id = delegation.delegator_id
                assignment = (
                    session.execute(
                        select(DocumentReviewer).where(
                            DocumentReviewer.review_cycle_id == cycle_id,
                            DocumentReviewer.reviewer_id == delegator_id,
                        )
                    )
                    .scalars()
                    .first()
                )

        if assignment is None:
            raise HTTPException(status_code=403, detail="reviewer not assigned")

        if delegator_id is not None:
            delegation = get_active_delegation(
                session, document.id, delegator_id, actor.id
            )
            if not delegation:
                raise HTTPException(status_code=400, detail="delegation has expired")

        if assignment.decision is not None:
            raise HTTPException(status_code=400, detail="decision already submitted")

        if document.status != "review":
            raise HTTPException(status_code=400, detail="document is not in review")

        reviewer_id = assignment.reviewer_id
        if payload.decision == "approve" and reviewer_id == document.author_id:
            raise HTTPException(status_code=400, detail="self-approval not permitted")

        if delegator_id is not None and delegator_id == document.author_id:
            raise HTTPException(status_code=400, detail="self-approval not permitted")

        assignment.decision = payload.decision
        assignment.decision_reason = payload.reason
        assignment.decision_at = now_utc()
        assignment.decided_by_id = actor.id

        update_document_status(session, document)
        if document.status == "review":
            pending = (
                session.execute(
                    select(DocumentReviewer).where(
                        DocumentReviewer.review_cycle_id == cycle_id,
                        DocumentReviewer.decision.is_(None),
                    )
                )
                .scalars()
                .all()
            )
            if not pending:
                update_document_status(session, document)
        if document.status != "review":
            document.next_escalation_at = None
        return build_document_response(session, document)


@app.post("/documents/{document_id}/delegate", response_model=DocumentResponse)
def delegate_review(document_id: int, payload: DelegateRequest) -> DocumentResponse:
    with SessionLocal.begin() as session:
        document = get_document(session, document_id)
        ensure_user(session, payload.delegator_id)
        ensure_user(session, payload.substitute_id)

        cycle_id = document.current_cycle_id
        if cycle_id is None or document.status != "review":
            raise HTTPException(status_code=400, detail="document is not in review")

        assignment = (
            session.execute(
                select(DocumentReviewer).where(
                    DocumentReviewer.review_cycle_id == cycle_id,
                    DocumentReviewer.reviewer_id == payload.delegator_id,
                )
            )
            .scalars()
            .first()
        )
        if assignment is None:
            delegation = (
                session.execute(
                    select(Delegation).where(
                        Delegation.document_id == document.id,
                        Delegation.substitute_id == payload.delegator_id,
                        Delegation.revoked_at.is_(None),
                    )
                )
                .scalars()
                .first()
            )
            if delegation and delegation.expires_at > now_utc():
                raise HTTPException(
                    status_code=400, detail="re-delegation not permitted"
                )
            raise HTTPException(status_code=403, detail="delegator is not a reviewer")
        if payload.substitute_id == payload.delegator_id:
            raise HTTPException(status_code=400, detail="cannot delegate to self")
        if assignment.decision is not None:
            raise HTTPException(status_code=400, detail="decision already submitted")

        existing = (
            session.execute(
                select(Delegation).where(
                    Delegation.document_id == document.id,
                    Delegation.delegator_id == payload.delegator_id,
                    Delegation.revoked_at.is_(None),
                )
            )
            .scalars()
            .all()
        )
        if any(d.expires_at > now_utc() for d in existing):
            raise HTTPException(status_code=400, detail="delegation already active")

        if (
            session.execute(
                select(Delegation).where(
                    Delegation.document_id == document.id,
                    Delegation.substitute_id == payload.delegator_id,
                    Delegation.revoked_at.is_(None),
                )
            )
            .scalars()
            .first()
        ):
            raise HTTPException(status_code=400, detail="re-delegation not permitted")

        delegation = Delegation(
            document=document,
            delegator_id=payload.delegator_id,
            substitute_id=payload.substitute_id,
            expires_at=payload.expires_at,
        )
        session.add(delegation)
        return build_document_response(session, document)


@app.post("/documents/{document_id}/delegate/revoke", response_model=DocumentResponse)
def revoke_delegation(
    document_id: int, payload: RevokeDelegationRequest
) -> DocumentResponse:
    with SessionLocal.begin() as session:
        document = get_document(session, document_id)
        delegation = (
            session.execute(
                select(Delegation).where(
                    Delegation.document_id == document.id,
                    Delegation.delegator_id == payload.delegator_id,
                    Delegation.revoked_at.is_(None),
                )
            )
            .scalars()
            .first()
        )
        if not delegation:
            raise HTTPException(status_code=404, detail="delegation not found")
        delegation.revoked_at = now_utc()
        return build_document_response(session, document)


@app.post("/documents/{document_id}/escalate", response_model=DocumentResponse)
def escalate_document(document_id: int, payload: EscalateRequest) -> DocumentResponse:
    with SessionLocal.begin() as session:
        document = get_document(session, document_id)
        if document.status != "review":
            raise HTTPException(status_code=400, detail="document is not in review")
        if document.next_escalation_at is None:
            raise HTTPException(status_code=400, detail="escalation not scheduled")
        if now_utc() < document.next_escalation_at:
            raise HTTPException(
                status_code=400, detail="escalation timeout not reached"
            )

        chain = parse_ids(document.escalation_chain_text)
        if document.escalation_index >= document.max_escalation_depth:
            raise HTTPException(status_code=400, detail="max escalation depth reached")
        if document.escalation_index >= len(chain):
            raise HTTPException(
                status_code=400, detail="no escalation approver configured"
            )

        cycle_id = document.current_cycle_id
        if cycle_id is None:
            raise HTTPException(status_code=400, detail="review cycle not initialized")

        escalated_to_id = chain[document.escalation_index]
        ensure_user(session, escalated_to_id)
        existing_assignment = (
            session.execute(
                select(DocumentReviewer).where(
                    DocumentReviewer.review_cycle_id == cycle_id,
                    DocumentReviewer.reviewer_id == escalated_to_id,
                )
            )
            .scalars()
            .first()
        )
        if not existing_assignment:
            session.add(
                DocumentReviewer(
                    document=document,
                    review_cycle_id=cycle_id,
                    reviewer_id=escalated_to_id,
                )
            )
            reviewer_ids = parse_ids(document.reviewer_ids_text)
            if escalated_to_id not in reviewer_ids:
                reviewer_ids.append(escalated_to_id)
                document.reviewer_ids_text = ids_to_text(reviewer_ids)

        create_notification(
            session,
            escalated_to_id,
            document.id,
            "document escalated for review",
        )

        session.add(
            EscalationEvent(
                document_id=document.id,
                review_cycle_id=cycle_id,
                escalated_to_id=escalated_to_id,
                depth=document.escalation_index + 1,
            )
        )
        session.flush()
        document.escalation_index += 1
        document.next_escalation_at = now_utc() + timedelta(
            seconds=document.escalation_timeout_seconds
        )
        return build_document_response(session, document)


@app.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(user_id: int) -> list[NotificationResponse]:
    with SessionLocal() as session:
        ensure_user(session, user_id)
        notifications = (
            session.execute(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.asc())
            )
            .scalars()
            .all()
        )
        return [NotificationResponse.model_validate(item) for item in notifications]
