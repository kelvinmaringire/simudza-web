from django.core.management.base import BaseCommand

from businesses.verification_workflow import monitor


class Command(BaseCommand):
    help = (
        "Email business owners whose listings are due for re-confirmation and "
        "report how many exceptions need a Simudza employee. Run daily."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Count reminders that would be sent without sending them.",
        )

    def handle(self, *args, **options):
        from history.context import change_context
        from history.models import ChangeLog

        with change_context(source=ChangeLog.Source.SYSTEM):
            result = monitor(dry_run=options["dry_run"])
        prefix = "[dry run] " if options["dry_run"] else ""
        self.stdout.write(
            f"{prefix}Owners due for a reminder: {result['reminders_due']}\n"
            f"{prefix}Reminders sent: {result['reminders_sent']}\n"
            f"Exceptions for staff to investigate: {result['exceptions']}"
        )
