"""The shapes the API sends and receives."""

from typing import Literal

from pydantic import BaseModel, Field

Status = Literal[
    "waiting", "in_progress", "awaiting_sign_off", "decided", "needs_handler"
]
RunStatus = Literal["running", "finished", "failed"]
TodoStatus = Literal["todo", "in_progress", "done", "left_for_handler"]
DocumentName = Literal["wording", "manual"]
Outcome = Literal["approve", "decline", "refer"]


class Item(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


class Plan(BaseModel):
    plan: str
    name: str
    trip_cancellation_max: float
    trip_delay_waiting_hours: int
    trip_delay_max: float
    baggage_delay_waiting_hours: int
    baggage_delay_max: float
    baggage_max: float
    per_item_limit: float
    passport_max: float
    emergency_medical_max: float
    deductible: float


class Trip(BaseModel):
    destination: str
    departs_on: str
    returns_on: str
    trip_cost: float


class Policy(BaseModel):
    policy_id: str
    plan: str
    add_ons: list[str]
    purchased_on: str
    trip: Trip
    travelers: list[str]
    limits: Plan


class PreviousClaim(BaseModel):
    claim_id: str
    filed_on: str
    incident_date: str
    claim_type: str
    summary: str
    outcome: str
    amount_paid: float


class Customer(BaseModel):
    customer_id: str
    name: str
    previous_claims: list[PreviousClaim]


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    can_approve_over_limit: bool


class Decision(BaseModel):
    decision: Outcome
    payout: float
    reason: str
    policy_section: str


class Payment(BaseModel):
    amount: float
    paid_at: str


class SignOff(BaseModel):
    handler_id: str
    handler_name: str
    signed_at: str


class ClaimSummary(BaseModel):
    claim_id: str
    claim_type: str
    summary: str
    customer_name: str
    amount_claimed: float
    status: Status
    decision: Outcome | None
    payout: float | None


class Section(BaseModel):
    number: int
    title: str


class Read(BaseModel):
    document: DocumentName
    section: int
    title: str


class ClaimDetail(BaseModel):
    claim_id: str
    claim_type: str
    summary: str
    story: str
    submitted_on: str
    incident_date: str
    incident_location: str
    amount_claimed: float
    items: list[Item]
    documents: list[Document]
    status: Status
    policy: Policy
    customer: Customer
    decision: Decision | None
    payment: Payment | None
    sign_off: SignOff | None
    reads: list[Read]


class Event(BaseModel):
    kind: str
    text: str
    created_at: str


class NewEvent(BaseModel):
    kind: str
    text: str


class NewDecision(BaseModel):
    decision: Outcome
    payout: float
    reason: str
    policy_section: str


class NewRead(BaseModel):
    document: DocumentName
    section: int


class NewPayment(BaseModel):
    amount: float


class NewSignOff(BaseModel):
    handler_id: str


class Todo(BaseModel):
    content: str
    status: TodoStatus


class Run(BaseModel):
    run_id: int
    started_at: str
    limit: int
    status: RunStatus
    summary: str
    todos: list[Todo]


class NewRun(BaseModel):
    limit: int = Field(ge=0)


class NewTodos(BaseModel):
    todos: list[Todo]


class NewRelease(BaseModel):
    reason: str


class NewFinish(BaseModel):
    summary: str
