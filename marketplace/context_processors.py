from marketplace.settings import (
    currency_symbol,
    get_marketplace_currency,
    get_tax_config,
)
from marketplace.tax import format_tax_rate, rate_percent


def cart_context(request):
    """Cart UI is Alpine + localStorage; sync is available for guests and members."""
    code = get_marketplace_currency()
    tax = get_tax_config()
    rate = rate_percent(tax.rate_percent)
    tax_active = bool(tax.enabled and rate > 0)
    return {
        "cart_can_sync": True,
        "currency_code": code,
        "currency_symbol": currency_symbol(code),
        "tax_enabled": tax_active,
        "tax_pricing_mode": tax.pricing_mode,
        "tax_rate": format_tax_rate(rate),
    }
