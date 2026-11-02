"""Server-side marketplace tax calculation. Money uses Decimal, never float."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from marketplace.settings import (
    MarketplaceCurrency,
    TaxPricingMode,
    get_marketplace_currency,
    get_tax_config,
)

MONEY_QUANT = Decimal("0.01")
RATE_QUANT = Decimal("0.0001")
MAX_TAX_RATE = Decimal("100")


def money(value) -> Decimal:
    return Decimal(str(value)).quantize(MONEY_QUANT, rounding=ROUND_HALF_UP)


def rate_percent(value) -> Decimal:
    return Decimal(str(value)).quantize(RATE_QUANT, rounding=ROUND_HALF_UP)


def format_tax_rate(value) -> str:
    """Human-readable percent without trailing zeros: 15, 15.5, not 15.5000."""
    quantized = rate_percent(value)
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


@dataclass(frozen=True)
class TaxBreakdown:
    enabled: bool
    pricing_mode: str
    rate_percent: Decimal
    tax_base: Decimal
    tax_amount: Decimal
    merchandise_subtotal: Decimal
    delivery_fee: Decimal
    total: Decimal
    currency: str

    @property
    def rate_decimal(self) -> Decimal:
        return (self.rate_percent / Decimal("100")).quantize(
            Decimal("0.000001"), rounding=ROUND_HALF_UP
        )


def calculate_tax(
    *,
    merchandise_subtotal,
    delivery_fee=Decimal("0"),
    enabled: bool | None = None,
    pricing_mode: str | None = None,
    rate_percent_value=None,
    currency: str | None = None,
) -> TaxBreakdown:
    """
    Compute tax for a merchandise subtotal.

    Tax applies to merchandise only. Delivery is added after tax so future
    delivery rules can plug into the same totals structure.

    Tax excluded: tax = base × r ; total = base + tax + delivery
    Tax included: tax = base × r / (1 + r) ; total = base + delivery
    Disabled / zero rate: tax = 0 ; total = base + delivery
    """
    config = get_tax_config()
    subtotal = money(merchandise_subtotal)
    fee = money(delivery_fee)
    is_enabled = config.enabled if enabled is None else bool(enabled)
    mode = pricing_mode or config.pricing_mode or TaxPricingMode.EXCLUDED
    rate = rate_percent(
        config.rate_percent if rate_percent_value is None else rate_percent_value
    )
    currency_code = (currency or get_marketplace_currency() or MarketplaceCurrency.ZAR).upper()

    if not is_enabled or rate <= 0 or subtotal <= 0:
        return TaxBreakdown(
            enabled=bool(is_enabled and rate > 0),
            pricing_mode=mode,
            rate_percent=rate if is_enabled else Decimal("0.00"),
            tax_base=subtotal,
            tax_amount=money(0),
            merchandise_subtotal=subtotal,
            delivery_fee=fee,
            total=money(subtotal + fee),
            currency=currency_code,
        )

    r = rate / Decimal("100")
    if mode == TaxPricingMode.INCLUDED:
        tax_amount = money(subtotal * r / (Decimal("1") + r))
        total = money(subtotal + fee)
    else:
        tax_amount = money(subtotal * r)
        total = money(subtotal + tax_amount + fee)

    return TaxBreakdown(
        enabled=True,
        pricing_mode=mode,
        rate_percent=rate,
        tax_base=subtotal,
        tax_amount=tax_amount,
        merchandise_subtotal=subtotal,
        delivery_fee=fee,
        total=total,
        currency=currency_code,
    )


def breakdown_from_snapshot(
    *,
    tax_enabled: bool,
    tax_pricing_mode: str,
    tax_rate,
    tax_base,
    tax_amount,
    merchandise_subtotal,
    delivery_fee,
    total,
    currency: str,
) -> TaxBreakdown:
    """Rebuild a TaxBreakdown from persisted checkout/order fields."""
    return TaxBreakdown(
        enabled=bool(tax_enabled),
        pricing_mode=tax_pricing_mode or TaxPricingMode.EXCLUDED,
        rate_percent=rate_percent(tax_rate or 0),
        tax_base=money(tax_base or 0),
        tax_amount=money(tax_amount or 0),
        merchandise_subtotal=money(merchandise_subtotal or 0),
        delivery_fee=money(delivery_fee or 0),
        total=money(total or 0),
        currency=(currency or MarketplaceCurrency.ZAR).upper(),
    )
