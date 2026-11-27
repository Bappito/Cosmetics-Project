"""``python manage.py load_sample_data``: put the sample formulas into the business database."""
import sqlite3
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from cosmetics_erp.db.sample_formulas import load_sample_formulas


class Command(BaseCommand):
    help = ("Replace the catalog, product trees, plan, purchase orders and records with the sample data. "
            "A copy of the database is saved first.")

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Do not ask for confirmation.")

    def handle(self, *args, **options):
        path = Path(settings.ERP_DB_PATH)
        if not options["yes"]:
            self.stdout.write(f"This replaces the products, orders and plan in {path}.")
            try:
                answer = input("Type yes to continue: ")
            except EOFError:
                answer = ""
            if answer.strip().lower() != "yes":
                raise CommandError("Nothing was changed.")

        conn = sqlite3.connect(path, timeout=30)
        try:
            if conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'").fetchone()[0]:
                backup = path.with_name(f"{path.name}.before-sample-data-{datetime.now():%Y%m%d-%H%M%S-%f}.bak")
                copy = sqlite3.connect(backup)
                try:
                    conn.backup(copy)
                finally:
                    copy.close()
                self.stdout.write(f"Saved a copy of the current data: {backup}")
            load_sample_formulas(conn)
        finally:
            conn.close()
        self.stdout.write(self.style.SUCCESS("Sample data loaded."))
