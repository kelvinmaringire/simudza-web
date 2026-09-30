from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase
from django.urls import reverse
from import_export.formats.base_formats import CSV, XLSX
from tablib import Dataset

from businesses.models import Business
from businesses.resources import BusinessResource
class BusinessResourceTests(TestCase):
    def setUp(self):
        self.business = Business.objects.create(
            name="Export Co",
            slug="export-co",
        )

    def test_export_reimport_round_trip(self):
        resource = BusinessResource()
        exported = resource.export(Business.objects.filter(pk=self.business.pk))
        reimport = resource.import_data(exported, dry_run=True)
        self.assertFalse(reimport.has_errors())
        self.assertEqual(reimport.totals["update"], 1)

    def test_invalid_verification_level_errors_on_dry_run(self):
        dataset = Dataset()
        dataset.headers = ["slug", "name", "verification_level"]
        dataset.append(["bad-level-co", "Bad", "not_a_real_level"])
        resource = BusinessResource()
        result = resource.import_data(dataset, dry_run=True, raise_errors=False)
        self.assertTrue(result.totals["error"] >= 1)

    def test_xlsx_export_loads(self):
        resource = BusinessResource()
        exported = resource.export(Business.objects.filter(pk=self.business.pk))
        xlsx = XLSX().export_data(exported)
        loaded = XLSX().create_dataset(xlsx)
        self.assertIn("slug", loaded.headers)


class AdminImportExportViewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_superuser(
            "staffie",
            "staff@example.com",
            "pass",
        )
        self.viewer = User.objects.create_user(
            "viewer",
            "view@example.com",
            "pass",
            is_staff=True,
        )
        self.viewer.user_permissions.clear()
        self.business = Business.objects.create(name="Admin Co", slug="admin-co")
        self.client = Client()
        self.admin_host = {"HTTP_HOST": "localhost"}

    def test_export_requires_staff(self):
        url = reverse("business:export", kwargs={"fmt": "csv"})
        self.client.force_login(self.viewer)
        response = self.client.get(url, **self.admin_host)
        self.assertIn(response.status_code, {403, 302})

    def test_staff_can_export_csv(self):
        url = reverse("business:export", kwargs={"fmt": "csv"})
        self.client.force_login(self.staff)
        response = self.client.get(url, **self.admin_host)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response["Content-Type"])

    def test_import_preview_then_confirm(self):
        resource = BusinessResource()
        dataset = Dataset()
        dataset.headers = ["slug", "name", "verification_level"]
        dataset.append(["import-co", "Import Co", "unverified"])
        csv_bytes = CSV().export_data(dataset).encode("utf-8")

        self.client.force_login(self.staff)
        import_url = reverse("business:import", kwargs={"fmt": "csv"})
        preview = self.client.post(
            import_url,
            {
                "import_file": SimpleUploadedFile(
                    "businesses.csv",
                    csv_bytes,
                    content_type="text/csv",
                )
            },
            **self.admin_host,
        )
        self.assertEqual(preview.status_code, 200)
        self.assertContains(preview, "Import preview")

        confirm_url = reverse("business:import_confirm", kwargs={"fmt": "csv"})
        confirm = self.client.post(confirm_url, **self.admin_host)
        self.assertEqual(confirm.status_code, 302)
        self.assertTrue(Business.objects.filter(slug="import-co").exists())
