from django.db import models
from django.urls import reverse
from wagtail.admin.panels import FieldPanel
from wagtail.fields import RichTextField
from wagtail.models import Page


class DirectoryListing(models.Model):
    """
    Directory presence for a product. Every product gets one automatically;
    toggle featured / show_in_directory rather than creating listings by hand.
    """

    product = models.OneToOneField(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="directory_listing",
    )

    featured = models.BooleanField(
        default=False,
    )

    show_in_directory = models.BooleanField(
        default=True,
        help_text="Uncheck to hide this product from the public directory.",
    )

    views = models.PositiveIntegerField(
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-featured",
            "product__name",
        ]
        verbose_name_plural = "directory listings"

    def __str__(self):
        return self.product.name

    def get_absolute_url(self):
        return reverse(
            "directory:product",
            kwargs={
                "slug": self.product.slug,
            },
        )


class DirectoryPage(Page):
    """CMS page for the public product directory (listing + search)."""

    intro = RichTextField(
        blank=True,
        help_text="Optional intro shown above the directory search and listings.",
    )

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
    ]

    parent_page_types = ["home.HomePage"]
    subpage_types = []
    max_count = 1

    class Meta:
        verbose_name = "Directory page"

    def serve(self, request, *args, **kwargs):
        # Public UI is handled by DirectoryIndexView at /directory/.
        from django.shortcuts import redirect

        return redirect("directory:index", permanent=False)
