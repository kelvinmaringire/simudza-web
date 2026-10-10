import re
from urllib.parse import parse_qs, urlparse

from django.core.exceptions import ValidationError
from django.db import models
from wagtail.admin.panels import FieldPanel
from wagtail.models import Orderable

YOUTUBE_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "music.youtube.com",
    "youtube-nocookie.com",
    "www.youtube-nocookie.com",
}

YOUTUBE_SHORT_HOSTS = {"youtu.be", "www.youtu.be"}

YOUTUBE_PATH_PREFIXES = ("embed", "shorts", "live", "v")


class BusinessVideoKind(models.TextChoices):
    """Videos about the company: who they are, where they work, what they can deliver."""

    BUSINESS_TOUR = "business_tour", "Factory or business tour"
    MANUFACTURING = "manufacturing", "Manufacturing process"
    PROJECT_PORTFOLIO = "project_portfolio", "Project portfolio"
    INTERVIEW = "interview", "Producer or business interview"
    CAPACITY_SUPPLY = "capacity_supply", "Products, capacity and supply"
    TESTIMONIAL = "testimonial", "Customer testimonial"
    ADVERTISEMENT = "advertisement", "Advertisement"
    OTHER = "other", "Other"


class ProductVideoKind(models.TextChoices):
    """Videos about one product or service: what it does and how to use it."""

    PRODUCT_DEMONSTRATION = "demonstration", "Product demonstration"
    SERVICE_DEMONSTRATION = "service_demonstration", "Service demonstration"
    HOW_TO = "how_to", "How-to and educational"
    MANUFACTURING = "manufacturing", "Manufacturing process"
    TESTIMONIAL = "testimonial", "Customer testimonial"
    ADVERTISEMENT = "advertisement", "Advertisement"
    OTHER = "other", "Other"


def youtube_video_id(url):
    """Return the 11-character YouTube video id for a URL, or None."""
    if not url:
        return None
    parsed = urlparse(url.strip())
    host = (parsed.hostname or "").lower()
    parts = [part for part in parsed.path.split("/") if part]

    candidate = None
    if host in YOUTUBE_SHORT_HOSTS:
        candidate = parts[0] if parts else None
    elif host in YOUTUBE_HOSTS:
        if parts[:1] == ["watch"]:
            candidate = parse_qs(parsed.query).get("v", [None])[0]
        elif len(parts) >= 2 and parts[0] in YOUTUBE_PATH_PREFIXES:
            candidate = parts[1]

    if candidate and YOUTUBE_ID_RE.match(candidate):
        return candidate
    return None


def validate_youtube_url(url):
    if not youtube_video_id(url):
        raise ValidationError(
            "Enter a YouTube video link, e.g. https://www.youtube.com/watch?v=… "
            "or https://youtu.be/…"
        )


class VideoLink(Orderable):
    """
    YouTube link attached to a listing. Subclasses add the ParentalKey and a
    ``kind`` field with their own choices.
    """

    url = models.URLField(
        "YouTube link",
        max_length=500,
        validators=[validate_youtube_url],
    )

    title = models.CharField(
        max_length=200,
        blank=True,
    )

    panels = [
        FieldPanel("url"),
        FieldPanel("title"),
        FieldPanel("kind"),
    ]

    class Meta(Orderable.Meta):
        abstract = True

    def __str__(self):
        return self.title or self.get_kind_display()

    @property
    def youtube_id(self):
        return youtube_video_id(self.url)

    @property
    def embed_url(self):
        video_id = self.youtube_id
        if not video_id:
            return ""
        return f"https://www.youtube-nocookie.com/embed/{video_id}"

    @property
    def watch_url(self):
        video_id = self.youtube_id
        if not video_id:
            return self.url
        return f"https://www.youtube.com/watch?v={video_id}"

    @property
    def display_title(self):
        return self.title or self.get_kind_display()
