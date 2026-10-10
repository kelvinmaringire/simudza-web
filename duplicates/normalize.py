"""
Normalisation helpers shared by duplicate detection.

Everything here is pure (no database access) so the same keys can be computed
for saved records and imports.
"""

import re
import unicodedata
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from urllib.parse import urlsplit

TOKEN_MATCH_RATIO = 0.85

PRODUCT_STOPWORDS = frozenset({"the", "and"})

BUSINESS_STOPWORDS = frozenset(
    {
        "the",
        "and",
        "pvt",
        "private",
        "ltd",
        "limited",
        "plc",
        "inc",
        "incorporated",
        "llc",
        "co",
        "company",
        "corp",
        "corporation",
        "zimbabwe",
        "zim",
        "zw",
    }
)

# Converted to a base unit so "1 l" and "1000 ml" compare equal.
SIZE_UNITS = {
    "ml": ("ml", 1),
    "millilitre": ("ml", 1),
    "millilitres": ("ml", 1),
    "milliliter": ("ml", 1),
    "milliliters": ("ml", 1),
    "cl": ("ml", 10),
    "l": ("ml", 1000),
    "lt": ("ml", 1000),
    "ltr": ("ml", 1000),
    "ltrs": ("ml", 1000),
    "litre": ("ml", 1000),
    "litres": ("ml", 1000),
    "liter": ("ml", 1000),
    "liters": ("ml", 1000),
    "g": ("g", 1),
    "gm": ("g", 1),
    "gms": ("g", 1),
    "gram": ("g", 1),
    "grams": ("g", 1),
    "kg": ("g", 1000),
    "kgs": ("g", 1000),
    "oz": ("oz", 1),
}

_SIZE_RE = re.compile(
    r"(?<![a-z0-9])(\d+(?:[.,]\d+)?)\s*("
    + "|".join(sorted(SIZE_UNITS, key=len, reverse=True))
    + r")(?![a-z0-9])"
)
_MULTIPACK_RE = re.compile(r"(?<![a-z0-9])(\d+)\s*x(?![a-z])")

FREE_EMAIL_DOMAINS = frozenset(
    {
        "gmail.com",
        "googlemail.com",
        "yahoo.com",
        "yahoo.co.uk",
        "ymail.com",
        "outlook.com",
        "hotmail.com",
        "live.com",
        "icloud.com",
        "me.com",
        "aol.com",
        "proton.me",
        "protonmail.com",
        "zol.co.zw",
        "mweb.co.zw",
        "yo.co.zw",
    }
)

# Hosts where many unrelated businesses share a domain; compare full URLs instead.
SHARED_WEB_HOSTS = frozenset(
    {
        "facebook.com",
        "fb.com",
        "instagram.com",
        "twitter.com",
        "x.com",
        "linkedin.com",
        "tiktok.com",
        "youtube.com",
        "wa.me",
        "whatsapp.com",
        "linktr.ee",
        "google.com",
        "wixsite.com",
        "wordpress.com",
        "blogspot.com",
    }
)

_SECOND_LEVEL_LABELS = frozenset({"co", "com", "org", "net", "ac", "gov", "edu"})


def fold(text):
    """Lowercase, strip accents and apostrophes, spell out '&'."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower().replace("&", " and ")
    return re.sub(r"['’`]", "", text)


def _tokens(text, stopwords):
    words = re.sub(r"[^a-z0-9]+", " ", text).split()
    kept = [w for w in words if w not in stopwords]
    return tuple(kept or words)


def canonical_size(value, unit):
    """'500', 'ml' -> '500ml'; '1', 'L' -> '1000ml'. Empty string if unknown."""
    if value in (None, ""):
        return ""
    try:
        amount = Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        return ""
    base_unit, factor = SIZE_UNITS.get((unit or "").strip().lower().rstrip("."), (None, None))
    if base_unit is None:
        return ""
    amount = (amount * factor).normalize()
    return f"{format(amount, 'f')}{base_unit}"


def product_name_key(name):
    """(tokens without sizes, set of canonical sizes mentioned in the name)."""
    text = fold(name)
    sizes = set()

    def take_size(match):
        size = canonical_size(match.group(1), match.group(2))
        if size:
            sizes.add(size)
        return " "

    def take_multipack(match):
        sizes.add(f"x{match.group(1)}")
        return " "

    text = _SIZE_RE.sub(take_size, text)
    text = _MULTIPACK_RE.sub(take_multipack, text)
    return _tokens(text, PRODUCT_STOPWORDS), frozenset(sizes)


def business_name_key(name):
    """(core tokens without legal/country words, all tokens)."""
    text = fold(name)
    return _tokens(text, BUSINESS_STOPWORDS), _tokens(text, frozenset())


def _tokens_match(a, b):
    if a == b:
        return True
    if a.isdigit() or b.isdigit() or min(len(a), len(b)) < 4:
        return False
    return SequenceMatcher(None, a, b).ratio() >= TOKEN_MATCH_RATIO


def name_similarity(a_tokens, b_tokens):
    """
    Word-level Dice similarity in [0, 1], tolerant of small typos and of
    spacing/hyphen differences ("Coca-Cola" == "Coca Cola" == "Cocacola").

    Returns (similarity, contained) where `contained` means every word of the
    shorter name appears in the longer one.
    """
    if not a_tokens or not b_tokens:
        return 0.0, False
    if "".join(a_tokens) == "".join(b_tokens):
        return 1.0, True
    remaining = list(b_tokens)
    matched = 0
    for token in a_tokens:
        for index, other in enumerate(remaining):
            if _tokens_match(token, other):
                matched += 1
                remaining.pop(index)
                break
    similarity = 2 * matched / (len(a_tokens) + len(b_tokens))
    contained = matched == min(len(a_tokens), len(b_tokens))
    return similarity, contained


def normalize_barcode(value):
    """Digits only, leading zeros dropped so UPC-A and EAN-13 forms compare equal."""
    digits = re.sub(r"\D", "", value or "")
    return digits.lstrip("0")


def normalize_sku(value):
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def normalize_phones(value):
    """Set of comparable numbers from a free-text phone field (may hold several)."""
    numbers = set()
    for part in re.split(r"[/,;]|\bor\b", value or ""):
        digits = re.sub(r"\D", "", part)
        if digits.startswith("00"):
            digits = digits[2:]
        if digits.startswith("0"):
            digits = "263" + digits[1:]
        if len(digits) >= 7:
            numbers.add(digits)
    return numbers


def _registrable_domain(host):
    labels = [label for label in host.split(".") if label]
    if len(labels) >= 3 and labels[-2] in _SECOND_LEVEL_LABELS:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def website_key(url):
    """
    Comparable identity for a website: the registrable domain
    ('https://shop.schweppes.co.zw/' -> 'schweppes.co.zw'), or the full
    host + path for shared hosts like Facebook pages.
    """
    url = (url or "").strip()
    if not url:
        return ""
    if "://" not in url:
        url = f"http://{url}"
    parts = urlsplit(url.lower())
    host = (parts.hostname or "").removeprefix("www.")
    if not host:
        return ""
    domain = _registrable_domain(host)
    if domain in SHARED_WEB_HOSTS:
        path = parts.path.rstrip("/")
        return f"{domain}{path}" if path else ""
    return domain


def email_domain(email):
    """Company email domain, or '' for free webmail providers."""
    _, _, domain = (email or "").strip().lower().rpartition("@")
    if not domain or domain in FREE_EMAIL_DOMAINS:
        return ""
    return _registrable_domain(domain)
