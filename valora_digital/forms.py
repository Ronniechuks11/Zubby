"""Server-side validation for the contact form."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .content import BUDGET_OPTIONS

EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]{2,}$")
PHONE_RE = re.compile(r"^\+?[0-9][0-9\s().\-]{6,22}[0-9]$")
CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# (min, max) lengths. The contact field has no minimum here: its format check
# below gives a more useful message than "too short".
LIMITS = {"name": (2, 80), "contact": (1, 120), "message": (10, 2000)}


@dataclass
class ContactSubmission:
    name: str = ""
    contact: str = ""
    budget: str = ""
    message: str = ""
    honeypot: str = ""
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def is_bot(self) -> bool:
        return bool(self.honeypot)

    @property
    def is_valid(self) -> bool:
        return not self.errors

    @property
    def contact_is_email(self) -> bool:
        return bool(EMAIL_RE.match(self.contact))

    def values(self) -> dict[str, str]:
        """Values safe to echo back into the form after a validation error."""
        return {
            "name": self.name,
            "contact": self.contact,
            "budget": self.budget,
            "message": self.message,
        }


def _clean(value: str | None, *, multiline: bool = False) -> str:
    text = CONTROL_CHARS_RE.sub("", (value or "").replace("\r\n", "\n").replace("\r", "\n"))
    if not multiline:
        text = " ".join(text.split())  # collapse whitespace, drop newlines
    return text.strip()


def validate_contact(form) -> ContactSubmission:
    sub = ContactSubmission(
        name=_clean(form.get("name")),
        contact=_clean(form.get("contact")),
        budget=_clean(form.get("budget")),
        message=_clean(form.get("message"), multiline=True),
        honeypot=(form.get("website") or "").strip(),
    )

    for key, label in (("name", "your name"), ("contact", "an email address or WhatsApp number"),
                       ("message", "a short message")):
        lo, hi = LIMITS[key]
        length = len(getattr(sub, key))
        if length == 0:
            sub.errors[key] = f"Please enter {label}."
        elif length < lo:
            sub.errors[key] = "That looks too short — please add a little more."
        elif length > hi:
            sub.errors[key] = f"Please keep this under {hi} characters."

    if "contact" not in sub.errors and not (
        EMAIL_RE.match(sub.contact) or PHONE_RE.match(sub.contact)
    ):
        sub.errors["contact"] = "Enter a valid email address or WhatsApp number."

    if sub.budget not in BUDGET_OPTIONS:
        sub.errors["budget"] = "Please choose a budget range."

    return sub
