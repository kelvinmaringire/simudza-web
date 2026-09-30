from wagtail import blocks
from wagtail.images.blocks import ImageChooserBlock


HERO_DEFAULTS = {
    "eyebrow": "Proudly Zimbabwean",
    "heading": "Discover and buy products made in Zimbabwe",
    "subheading": (
        "Simudza connects you with local businesses and the products they "
        "make, grow, package and assemble — so every purchase helps build "
        "Zimbabwe."
    ),
    "primary_cta": {
        "label": "Explore products",
        "page": None,
        "link_url": "/directory/",
    },
    "secondary_cta": {
        "label": "Browse businesses",
        "page": None,
        "link_url": "/businesses/",
    },
    "image": None,
    "image_position": "right",
}


class LinkStructValue(blocks.StructValue):
    @property
    def href(self):
        page = self.get("page")
        if page:
            return page.url
        return (self.get("link_url") or "").strip()


class LinkBlock(blocks.StructBlock):
    """Button link to an internal page, or to a path / external URL."""

    label = blocks.CharBlock(
        required=False,
        max_length=60,
        help_text="The button is hidden when the label or link is empty.",
    )
    page = blocks.PageChooserBlock(
        required=False,
        help_text="Internal page to link to. Takes priority over the URL below.",
    )
    link_url = blocks.CharBlock(
        required=False,
        max_length=255,
        label="URL",
        help_text='A path such as "/directory/" or a full URL.',
    )

    class Meta:
        icon = "link"
        value_class = LinkStructValue


class HeroBlock(blocks.StructBlock):
    """Full-width page intro based on the daisyUI hero component."""

    eyebrow = blocks.CharBlock(
        required=False,
        max_length=60,
        default=HERO_DEFAULTS["eyebrow"],
        help_text="Short label shown above the heading.",
    )
    heading = blocks.CharBlock(
        max_length=120,
        default=HERO_DEFAULTS["heading"],
    )
    subheading = blocks.TextBlock(
        required=False,
        default=HERO_DEFAULTS["subheading"],
    )
    primary_cta = LinkBlock(
        label="Primary button",
        default=HERO_DEFAULTS["primary_cta"],
    )
    secondary_cta = LinkBlock(
        label="Secondary button",
        default=HERO_DEFAULTS["secondary_cta"],
    )
    image = ImageChooserBlock(
        required=False,
        help_text="Optional. Without an image the hero is centred.",
    )
    image_position = blocks.ChoiceBlock(
        choices=[("right", "Right"), ("left", "Left")],
        default=HERO_DEFAULTS["image_position"],
        help_text="Image side on large screens. On mobile it sits below the text.",
    )

    class Meta:
        icon = "pick"
        label = "Hero"
        template = "home/blocks/hero.html"


class HomeStreamBlock(blocks.StreamBlock):
    hero = HeroBlock()

    class Meta:
        block_counts = {
            "hero": {"max_num": 1},
        }


DEFAULT_HOME_BODY = [
    {"type": "hero", "value": HERO_DEFAULTS},
]
