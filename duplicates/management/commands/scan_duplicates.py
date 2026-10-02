from django.core.management.base import BaseCommand

from duplicates.services import scan_for_duplicates


class Command(BaseCommand):
    help = (
        "Re-check all businesses and products for possible duplicates and flag "
        "them for review. Never edits or deletes listings."
    )

    def add_arguments(self, parser):
        parser.add_argument("--businesses-only", action="store_true")
        parser.add_argument("--products-only", action="store_true")

    def handle(self, *args, **options):
        result = scan_for_duplicates(
            businesses=not options["products_only"],
            products=not options["businesses_only"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Checked {result.businesses_checked} businesses and "
                f"{result.products_checked} products. "
                f"{result.open_flags} possible duplicates need review."
            )
        )
