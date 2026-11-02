from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.forms.widgets import NumberInput
from wagtail.admin.panels import FieldPanel
from wagtail.contrib.settings.models import BaseGenericSetting, register_setting

from simudza.utils.admin_grid import GridPanel, GridRow


class MarketplaceCurrency(models.TextChoices):
    ZAR = "ZAR", "South African Rand (ZAR)"
    USD = "USD", "US Dollar (USD)"


class TaxPricingMode(models.TextChoices):
    EXCLUDED = "excluded", "Tax excluded — add tax on top of product prices"
    INCLUDED = "included", "Tax included — product prices already include tax"


class CompactTaxRateInput(NumberInput):
    """Render tax rate without trailing zeros (15 / 15.5, not 15.5000)."""

    def __init__(self, attrs=None):
        defaults = {"step": "any"}
        if attrs:
            defaults.update(attrs)
        super().__init__(attrs=defaults)

    def format_value(self, value):
        if value in (None, ""):
            return None
        from marketplace.tax import format_tax_rate

        return format_tax_rate(value)


@register_setting(icon="shopping-cart")
class MarketplaceSettings(BaseGenericSetting):
    """Site-wide marketplace checkout settings (Wagtail Settings)."""

    currency = models.CharField(
        max_length=3,
        choices=MarketplaceCurrency.choices,
        default=MarketplaceCurrency.ZAR,
        help_text=(
            "Currency sent to Paystack. Must match a currency enabled on your "
            "Paystack merchant account (South African accounts usually use ZAR)."
        ),
    )
    tax_enabled = models.BooleanField(
        default=False,
        help_text="When off, checkout totals exclude tax and no tax line is shown.",
    )
    tax_pricing_mode = models.CharField(
        max_length=20,
        choices=TaxPricingMode.choices,
        default=TaxPricingMode.EXCLUDED,
        help_text=(
            "Tax excluded: product prices exclude tax; tax is added at checkout. "
            "Tax included: product prices already include tax; tax is extracted for "
            "display but not added again."
        ),
    )
    tax_rate = models.DecimalField(
        max_digits=6,
        decimal_places=4,
        default=Decimal("0.0000"),
        validators=[
            MinValueValidator(Decimal("0")),
            MaxValueValidator(Decimal("100")),
        ],
        help_text="Tax rate as a percentage, e.g. 15 or 15.5. Must be between 0 and 100.",
    )
    collection_enabled = models.BooleanField(
        default=True,
        help_text=(
            "When on, customers can choose collection at checkout. "
            "When off, only delivery is offered."
        ),
    )

    panels = [
        GridPanel(
            [
                GridRow(
                    [
                        FieldPanel("currency"),
                        FieldPanel("collection_enabled"),
                    ]
                ),
            ],
            heading="Checkout",
        ),
        GridPanel(
            [
                GridRow(
                    [
                        FieldPanel("tax_enabled"),
                        FieldPanel("tax_rate", widget=CompactTaxRateInput),
                    ]
                ),
                FieldPanel("tax_pricing_mode"),
            ],
            heading="Tax",
        ),
    ]

    class Meta:
        verbose_name = "Marketplace"

    def clean(self):
        super().clean()
        if self.tax_rate is None:
            raise ValidationError({"tax_rate": "Enter a tax rate."})
        if self.tax_rate < 0 or self.tax_rate > 100:
            raise ValidationError({"tax_rate": "Tax rate must be between 0 and 100."})
        if self.tax_enabled and self.tax_pricing_mode not in TaxPricingMode.values:
            raise ValidationError({"tax_pricing_mode": "Choose a tax pricing mode."})


def get_marketplace_settings():
    try:
        return MarketplaceSettings.load()
    except Exception:
        return None


def get_marketplace_currency() -> str:
    """Active checkout currency from Wagtail Settings, else Django env default."""
    settings_obj = get_marketplace_settings()
    if settings_obj and settings_obj.currency:
        return settings_obj.currency
    from django.conf import settings

    return getattr(settings, "PAYSTACK_CURRENCY", MarketplaceCurrency.ZAR) or (
        MarketplaceCurrency.ZAR
    )


def is_collection_enabled() -> bool:
    """Whether checkout may offer collection. Defaults on if settings are missing."""
    settings_obj = get_marketplace_settings()
    if settings_obj is None:
        return True
    return bool(settings_obj.collection_enabled)


def currency_symbol(code: str | None = None) -> str:
    code = (code or get_marketplace_currency()).upper()
    if code == MarketplaceCurrency.ZAR:
        return "R"
    return "$"


class TaxConfig:
    __slots__ = ("enabled", "pricing_mode", "rate_percent")

    def __init__(self, *, enabled: bool, pricing_mode: str, rate_percent: Decimal):
        self.enabled = enabled
        self.pricing_mode = pricing_mode
        self.rate_percent = rate_percent


def get_tax_config() -> TaxConfig:
    settings_obj = get_marketplace_settings()
    if settings_obj is None:
        return TaxConfig(
            enabled=False,
            pricing_mode=TaxPricingMode.EXCLUDED,
            rate_percent=Decimal("0"),
        )
    return TaxConfig(
        enabled=bool(settings_obj.tax_enabled),
        pricing_mode=settings_obj.tax_pricing_mode or TaxPricingMode.EXCLUDED,
        rate_percent=Decimal(str(settings_obj.tax_rate or 0)),
    )
