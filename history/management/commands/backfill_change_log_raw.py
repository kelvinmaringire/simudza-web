from django.core.management.base import BaseCommand

from history.backfill import backfill_raw_values


class Command(BaseCommand):
    help = "Make older change log field updates undoable where their values can be recovered exactly."

    def handle(self, *args, **options):
        count = backfill_raw_values()
        self.stdout.write(self.style.SUCCESS(f"Backfilled {count} change log entries."))
