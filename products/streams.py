from django.utils.text import slugify
from wagtail import blocks


class ClassificationSectionBlock(blocks.StructBlock):
    """One classification type with definition, optional flow, examples, and notes."""

    title = blocks.CharBlock(
        max_length=120,
        help_text='Classification name, e.g. "Made in Zimbabwe".',
    )
    anchor_slug = blocks.CharBlock(
        required=False,
        max_length=120,
        help_text="Optional URL anchor. Leave blank to generate from the title.",
    )
    definition = blocks.TextBlock(
        help_text="What this classification means.",
    )
    steps = blocks.ListBlock(
        blocks.CharBlock(label="Step", max_length=200),
        required=False,
        default=[],
        help_text="Optional process steps (useful for Packaged / Assembled).",
    )
    examples = blocks.ListBlock(
        blocks.CharBlock(label="Example", max_length=300),
        required=False,
        default=[],
        help_text="Concrete examples of this classification.",
    )
    notes = blocks.ListBlock(
        blocks.TextBlock(label="Note"),
        required=False,
        default=[],
        help_text="Limitations, distinctions, or extra guidance.",
    )

    class Meta:
        icon = "list-ul"
        label = "Classification"
        template = "products/blocks/classification_section.html"

    def get_context(self, value, parent_context=None):
        context = super().get_context(value, parent_context=parent_context)
        anchor = (value.get("anchor_slug") or "").strip()
        if not anchor:
            anchor = slugify(value.get("title") or "") or "section"
        context["anchor"] = anchor
        return context


class ImportantNoteBlock(blocks.StructBlock):
    """Prominent callout, e.g. classifications are not quality ratings."""

    text = blocks.TextBlock(
        help_text="Shown as a highlighted note near the top of the page.",
    )

    class Meta:
        icon = "warning"
        label = "Important note"
        template = "products/blocks/important_note.html"


class ProductClassificationStreamBlock(blocks.StreamBlock):
    important_note = ImportantNoteBlock()
    classification = ClassificationSectionBlock()

    class Meta:
        block_counts = {
            "important_note": {"max_num": 1},
        }


DEFAULT_PRODUCT_CLASSIFICATION_BODY = [
    {
        "type": "important_note",
        "value": {
            "text": (
                "These classifications are not quality ratings. A product can "
                "have more than one classification."
            ),
        },
    },
    {
        "type": "classification",
        "value": {
            "title": "Made in Zimbabwe",
            "anchor_slug": "made-in-zimbabwe",
            "definition": (
                "The product is substantially manufactured or processed in "
                "Zimbabwe."
            ),
            "steps": [],
            "examples": [
                "A biscuit manufactured and finished in Zimbabwe",
                "A garment cut, sewn, and finished in Zimbabwe",
                "A processed food whose primary manufacturing steps happen in Zimbabwe",
            ],
            "notes": [],
        },
    },
    {
        "type": "classification",
        "value": {
            "title": "Grown in Zimbabwe",
            "anchor_slug": "grown-in-zimbabwe",
            "definition": (
                "The primary agricultural or plant-based raw material is "
                "produced in Zimbabwe."
            ),
            "steps": [],
            "examples": [
                "Cotton",
                "Maize",
                "Wheat",
                "Tobacco",
                "Sugar cane",
                "Tea",
                "Coffee",
                "Fruits",
                "Vegetables",
                "Livestock products",
            ],
            "notes": [
                "This classification focuses on where the primary agricultural "
                "or plant-based material is produced, not on later "
                "manufacturing alone.",
            ],
        },
    },
    {
        "type": "classification",
        "value": {
            "title": "Packaged in Zimbabwe",
            "anchor_slug": "packaged-in-zimbabwe",
            "definition": (
                "The product is manufactured or produced elsewhere, but the "
                "final packaging operation occurs in Zimbabwe."
            ),
            "steps": [
                "Product manufactured abroad",
                "Bulk imported",
                "Packaged in Zimbabwe",
                "Sold as finished product",
            ],
            "examples": [
                "A product manufactured abroad, bulk imported, then packaged "
                "and labeled in Zimbabwe for sale as a finished product",
            ],
            "notes": [
                "Packaged in Zimbabwe is distinct from Assembled in Zimbabwe. "
                "They describe different kinds of economic activity and are "
                "not interchangeable.",
            ],
        },
    },
    {
        "type": "classification",
        "value": {
            "title": "Assembled in Zimbabwe",
            "anchor_slug": "assembled-in-zimbabwe",
            "definition": (
                "The components are manufactured elsewhere, but the final "
                "assembly happens in Zimbabwe."
            ),
            "steps": [
                "Components imported",
                "Assembled in Zimbabwe",
                "Finished product",
            ],
            "examples": [
                "Imported components assembled into a finished product in Zimbabwe",
            ],
            "notes": [
                "Assembled in Zimbabwe is distinct from Packaged in Zimbabwe. "
                "Assembly means putting components together into a finished "
                "product; packaging means final packing or labeling of a "
                "product made elsewhere.",
            ],
        },
    },
    {
        "type": "classification",
        "value": {
            "title": "Supports Zimbabwe",
            "anchor_slug": "supports-zimbabwe",
            "definition": (
                "The product does not meet the stronger production criteria "
                "above, but there is a documented Zimbabwean economic or "
                "business connection."
            ),
            "steps": [],
            "examples": [
                "A product with a clear Zimbabwean business, ownership, or "
                "economic link that is documented, even when primary "
                "production happens elsewhere",
            ],
            "notes": [
                "This is a narrower claim than Made, Grown, Packaged, or "
                "Assembled in Zimbabwe. It should only be used when that "
                "documented connection exists and the stronger production "
                "classifications do not apply.",
            ],
        },
    },
    {
        "type": "classification",
        "value": {
            "title": "Other",
            "anchor_slug": "other",
            "definition": "The product does not fit the defined classifications.",
            "steps": [],
            "examples": [
                "Edge cases that cannot be placed honestly in the classifications above",
            ],
            "notes": [],
        },
    },
]
