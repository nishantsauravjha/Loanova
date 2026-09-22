from typing import TypedDict


REQUIRED_FIELDS = [
    "business_type",
    "time_in_operation",
    "monthly_revenue",
    "requested_amount",
    "use_of_funds",
]


class LoanQualificationState(TypedDict, total=False):
    question: str
    business_type: str
    time_in_operation: str
    monthly_revenue: str
    requested_amount: str
    use_of_funds: str
    missing_fields: list[str]
    objection: str
    escalate: bool
    status: str
    answer: str
