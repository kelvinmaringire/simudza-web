from django.core.management.base import BaseCommand

from businesses.models import Business
from businesses.quality import refresh_business_quality
from products.models import Product
from products.quality import refresh_product_quality

BATCH = 500


class Command(BaseCommand):
    help = "Recompute stored data-quality scores for all businesses and products."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count rows only; do not write scores.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        business_count = Business.objects.count()
        product_count = Product.objects.count()
        if dry_run:
            self.stdout.write(
                f"Would refresh {business_count} businesses and {product_count} products."
            )
            return

        refreshed_b = 0
        last_pk = 0
        while True:
            batch = list(
                Business.objects.filter(pk__gt=last_pk).order_by("pk")[:BATCH]
            )
            if not batch:
                break
            refresh_business_quality(Business.objects.filter(pk__in=[b.pk for b in batch]))
            refreshed_b += len(batch)
            last_pk = batch[-1].pk

        refresh_product_quality(Product.objects.all(), batch_size=BATCH)
        refreshed_p = product_count

        self.stdout.write(
            self.style.SUCCESS(
                f"Refreshed {refreshed_b} businesses and {refreshed_p} products."
            )
        )
