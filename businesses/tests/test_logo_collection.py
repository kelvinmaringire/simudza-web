import io
import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image as PILImage
from wagtail.models import Collection

from businesses.models import Business
from businesses.services import owner_save_company
from simudza.utils.collections import business_logo_collection

MEDIA_ROOT = tempfile.mkdtemp()


def _png_upload(name="logo.png"):
    buffer = io.BytesIO()
    PILImage.new("RGB", (4, 4), "red").save(buffer, format="PNG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/png")


@override_settings(MEDIA_ROOT=MEDIA_ROOT, BUSINESS_LOGO_COLLECTION_NAME="Businesses")
class BusinessLogoCollectionTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = get_user_model().objects.create_user("owner", "o@example.com", "pass")
        self.root = Collection.get_first_root_node()

    def _save_with_logo(self, name="Logo Co"):
        return owner_save_company(
            self.user,
            {"name": name, "business_type": "manufacturer"},
            logo_upload=_png_upload(),
        )

    def _top_level(self, name):
        return Collection.objects.filter(depth=2, name=name)

    def test_logo_saved_in_existing_businesses_collection(self):
        collection = self.root.add_child(name="Businesses")
        business = self._save_with_logo()
        self.assertEqual(business.logo.collection, collection)

    def test_lookup_is_by_name_not_id(self):
        self.root.add_child(name="Homepage")
        self.root.add_child(name="Products")
        collection = self.root.add_child(name="Businesses")
        business = self._save_with_logo()
        self.assertEqual(business.logo.collection_id, collection.pk)
        self.assertEqual(business.logo.collection.name, "Businesses")

    def test_lookup_is_case_insensitive(self):
        collection = self.root.add_child(name="businesses")
        self.assertEqual(business_logo_collection(), collection)
        self.assertEqual(self._top_level("Businesses").count(), 0)

    def test_missing_collection_is_created_under_root(self):
        self.assertFalse(self._top_level("Businesses").exists())
        business = self._save_with_logo()
        collection = business.logo.collection
        self.assertEqual(collection.name, "Businesses")
        self.assertEqual(collection.get_parent(), self.root)

    def test_repeat_uploads_reuse_one_collection(self):
        first = self._save_with_logo("First Co")
        second = self._save_with_logo("Second Co")
        self.assertEqual(first.logo.collection, second.logo.collection)
        self.assertEqual(self._top_level("Businesses").count(), 1)

    def test_renamed_collection_does_not_break_uploads(self):
        old = self.root.add_child(name="Businesses")
        old.name = "Old Logos"
        old.save()
        business = self._save_with_logo()
        self.assertNotEqual(business.logo.collection, old)
        self.assertEqual(business.logo.collection.name, "Businesses")

    def test_deleted_and_recreated_collection_gets_new_id(self):
        old = self.root.add_child(name="Businesses")
        old_pk = old.pk
        old.delete()
        recreated = self.root.add_child(name="Businesses")
        self.assertNotEqual(recreated.pk, old_pk)
        business = self._save_with_logo()
        self.assertEqual(business.logo.collection, recreated)

    def test_nested_collection_with_same_name_is_ignored(self):
        parent = self.root.add_child(name="Archive")
        nested = parent.add_child(name="Businesses")
        business = self._save_with_logo()
        self.assertNotEqual(business.logo.collection, nested)
        self.assertEqual(business.logo.collection.get_parent(), self.root)

    @override_settings(BUSINESS_LOGO_COLLECTION_NAME="Company Logos")
    def test_collection_name_comes_from_settings(self):
        business = self._save_with_logo()
        self.assertEqual(business.logo.collection.name, "Company Logos")

    def test_no_upload_creates_no_collection(self):
        owner_save_company(self.user, {"name": "No Logo", "business_type": "manufacturer"})
        self.assertFalse(self._top_level("Businesses").exists())

    def test_submit_company_view_puts_logo_in_businesses_collection(self):
        collection = self.root.add_child(name="Businesses")
        self.client.force_login(self.user)
        response = self.client.post(
            reverse("businesses:submit_company"),
            {
                "name": "Posted Co",
                "business_type": "manufacturer",
                "logo_upload": _png_upload(),
            },
        )
        self.assertEqual(response.status_code, 302, getattr(response, "context", None))
        business = Business.objects.get(name="Posted Co")
        self.assertEqual(business.logo.collection, collection)
