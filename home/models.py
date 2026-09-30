from wagtail.admin.panels import FieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page

from .streams import HomeStreamBlock


class HomePage(Page):
    body = StreamField(
        HomeStreamBlock(),
        blank=True,
    )

    content_panels = Page.content_panels + [
        FieldPanel("body"),
    ]
