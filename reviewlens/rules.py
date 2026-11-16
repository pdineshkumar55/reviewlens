"""Deterministic rules that sit alongside the classifier.

* Health/safety escalation: certain keywords force urgency to ``high``.
* Reply safety: suggested replies must not promise money, admit liability,
  argue, or include contact details other than the configured support contact.
* Fallback replies used when a safe reply cannot be obtained.
* PII masking for anything written to logs.
"""

from __future__ import annotations

import re

# Keywords are matched against word tokens of the review text (lowercased).
#   prefix: matches any token that starts with the keyword ("vomit" -> "vomiting")
#   exact:  matches whole tokens only ("mudi" must not match "mudinjuthu")
#   phrase: multi-word phrases matched on the token stream
SAFETY_PREFIX = [
    # English
    "poison",
    "vomit",
    "diarrh",
    "allerg",
    "hospital",
    "insect",
    "cockroach",
    "worm",
    "maggot",
    "injur",
    "lawyer",
    "legal",
    "lawsuit",
    "fssai",
    # Tanglish
    "vaanthi",
    "vandhi",
    "poochi",
    "karappan",
    "hospitalla",
    "aaspathri",
    # Tamil script
    "வாந்தி",
    "பூச்சி",
    "கரப்பான்",
    "மருத்துவமனை",
    "ஹாஸ்பிடல்",
    "ஆஸ்பத்திரி",
    "ஒவ்வாமை",
    "அலர்ஜி",
    "புழு",
    "விஷ",
    "வழக்கு",
    "நீதிமன்ற",
    "போலீஸ்",
]
SAFETY_EXACT = [
    "hair",
    "hairs",
    "fly",
    "flies",
    "sue",
    "police",
    "mudi",
    "முடி",
]
SAFETY_PHRASES = [
    "food poisoning",
    "stomach pain",
    "stomach upset",
    "loose motion",
    "fell ill",
    "got sick",
    "fell sick",
    "felt sick",
    "became sick",
    "consumer court",
    "vayiru vali",
    "vayiru valikudhu",
    "vayiru sari illa",
    "வயிற்று வலி",
    "வயிறு வலி",
]

_TOKEN_RE = re.compile(r"[^\s.,!?;:\"'()\[\]{}/\\|*_+=<>~`@#$%^&-]+")


def _tokens(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def safety_hits(text: str) -> list[str]:
    """Return the health/safety keywords found in a review (empty if none)."""
    tokens = _tokens(text)
    joined = " " + " ".join(tokens) + " "
    hits: list[str] = []
    for kw in SAFETY_PREFIX:
        if any(t.startswith(kw) for t in tokens):
            hits.append(kw)
    for kw in SAFETY_EXACT:
        if kw in tokens:
            hits.append(kw)
    for phrase in SAFETY_PHRASES:
        if f" {phrase} " in joined:
            hits.append(phrase)
    return hits


def forced_high_urgency(text: str) -> bool:
    return bool(safety_hits(text))


# --- Reply safety -----------------------------------------------------------

_UNSAFE_REPLY = [
    # Acknowledging a refund request is fine; promising one is not.
    (r"\b(we will|we'll|we shall|we are going to|we can|we have)\s+(\w+\s+)?(refund|reimburse)", "promises a refund"),
    (r"\b(process|issue|initiate|arrange|approve)\w*\s+(a\s+|your\s+|the\s+)?(full\s+)?refund", "promises a refund"),
    (
        r"\brefund\s+(will be|has been|is being|is)\s+(processed|issued|initiated|credited|approved)",
        "promises a refund",
    ),
    (r"\bfull refund\b", "promises a refund"),
    (r"\bmoney back\b", "promises money back"),
    (r"\bdiscount", "offers a discount"),
    (r"\b(coupon|voucher|promo code|cashback)", "offers a coupon or voucher"),
    (r"\bcompensat", "offers compensation"),
    (r"\b(free (meal|order|food|delivery|dessert))\b", "offers something free"),
    (r"\bon the house\b", "offers something free"),
    (r"(₹|\brs\.?|\binr)\s?\d", "names an amount"),
    (r"\$\s?\d", "names an amount"),
    (r"\b(accept|take) (full |complete )?(responsibility|liability)\b", "admits liability"),
    (r"\b(we are|we're) (liable|responsible for)\b", "admits liability"),
    (r"\b(it was|this was|that was) (entirely |completely )?our fault\b", "admits liability"),
    (r"\byou are (wrong|lying)\b", "argues with the customer"),
    (r"\b(that's|that is|this is) not true\b", "argues with the customer"),
    (r"\bnot our fault\b", "argues with the customer"),
    (r"https?://|www\.", "contains a link"),
    (r"[\w.+-]+@[\w-]+\.[\w.-]+", "contains an email address"),
    (r"\+?\d[\d\s-]{7,}\d", "contains a phone number"),
]
_UNSAFE_RE = [(re.compile(p, re.IGNORECASE), why) for p, why in _UNSAFE_REPLY]


def reply_problems(reply: str, support_contact: str = "") -> list[str]:
    text = reply or ""
    if support_contact:
        text = text.replace(support_contact, "")
    return sorted({why for rx, why in _UNSAFE_RE if rx.search(text)})


_FALLBACK = {
    "delivery": (
        "We are sorry your order did not reach you the way it should have. "
        "Please DM us your order ID so our team can look into it."
    ),
    "food_quality": (
        "We are sorry the food did not meet your expectations. Please DM us your order ID so our team can look into it."
    ),
    "price": (
        "We are sorry about the confusion with your bill. Please DM us your order ID so our team can check the charges."
    ),
    "staff": ("We are sorry about your experience with our team. Please DM us the details so we can look into it."),
    "packaging": (
        "We are sorry your order was not packed well. Please DM us your order ID so our team can look into it."
    ),
    "app": (
        "We are sorry you had trouble while ordering. Please DM us your order ID and the issue so our team can help."
    ),
}
_FALLBACK_POSITIVE = "Thank you for your kind words. We look forward to serving you again."
_FALLBACK_NEUTRAL = "Thank you for your feedback. We will share it with our team."


def fallback_reply(category: str, sentiment: str, support_contact: str = "") -> str:
    if sentiment == "positive":
        return _FALLBACK_POSITIVE
    if sentiment == "neutral":
        return _FALLBACK_NEUTRAL
    reply = _FALLBACK.get(category, _FALLBACK["food_quality"])
    if support_contact:
        reply = reply.rstrip(".") + f", or reach us at {support_contact}."
    return reply


# --- Log masking ------------------------------------------------------------

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE_RE = re.compile(r"\+?\d[\d\s-]{7,}\d")


def mask_pii(text: str) -> str:
    text = _EMAIL_RE.sub("[email]", text or "")
    return _PHONE_RE.sub("[phone]", text)
