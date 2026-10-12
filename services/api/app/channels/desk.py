"""The call-taker's paste/type form (P0). Calls typed in, and WhatsApp forwards pasted in, as a volunteer
desk works today. Keyword chips fill in live as they type (preview arrives with the keyword path, m18)."""

from typing import Literal

from pydantic import BaseModel, Field

from app.channels.registry import adapter
from app.contracts import CanonicalReport, Content, Reporter, Source


class DeskReport(BaseModel):
    incident: str = Field(pattern=r"^[A-Z]{2,4}$")
    text: str = Field(min_length=1, max_length=5000)
    client_id: str = Field(min_length=8, max_length=100)        # the form's own id: retries never duplicate
    phone: str | None = Field(default=None, max_length=40)
    reporter_name: str | None = Field(default=None, max_length=200)
    relation: Literal["self", "family", "neighbour", "volunteer", "forwarder", "official", "unknown"] = "unknown"
    pasted_forward: bool = False


@adapter("desk")
def to_canonical(body: DeskReport) -> CanonicalReport:
    return CanonicalReport(
        schema_version="1", idempotency_key=body.client_id, channel="web_form", incident_hint=body.incident,
        reporter=Reporter(phone=body.phone, name=body.reporter_name,
                          relation="forwarder" if body.pasted_forward else body.relation),
        content=Content(text=body.text), source=Source(system="desk"))
