"""
Tests for the cloud storage layer (problems/storage) and PolygonAPI.migrate_to_storage.

S3/R2 calls are intercepted by moto, so no real bucket or credentials are needed:
    python manage.py test problems
"""

from unittest import mock

import boto3
from django.test import SimpleTestCase, override_settings
from moto import mock_aws

from problems.polygon_api import PolygonAPI
from problems.storage import StorageError, TestCaseStorage, get_storage
from problems.storage.s3 import S3CompatibleStorage

BUCKET = "test-bucket"


class KeyLayoutTests(SimpleTestCase):
    def test_input_and_output_keys_follow_required_layout(self):
        self.assertEqual(TestCaseStorage.input_key(42, 1), "test_cases/42/01")
        self.assertEqual(TestCaseStorage.output_key(42, 1), "test_cases/42/01.a")
        self.assertEqual(TestCaseStorage.input_key(42, 13), "test_cases/42/13")
        self.assertEqual(TestCaseStorage.problem_prefix(42), "test_cases/42/")


@override_settings(
    STORAGE_PROVIDER="r2",
    R2_ACCOUNT_ID="abc123",
    R2_ACCESS_KEY_ID="test-key",
    R2_SECRET_ACCESS_KEY="test-secret",
    R2_BUCKET_NAME=BUCKET,
    R2_ENDPOINT_URL=None,
)
class FactoryTests(SimpleTestCase):
    def test_r2_uses_account_endpoint(self):
        storage = get_storage()
        self.assertIsInstance(storage, S3CompatibleStorage)
        self.assertEqual(storage.location(), f"r2://{BUCKET}")
        self.assertEqual(
            storage._client.meta.endpoint_url, "https://abc123.r2.cloudflarestorage.com"
        )

    @override_settings(R2_ACCOUNT_ID="")
    def test_missing_account_id_is_a_clear_error(self):
        with self.assertRaisesMessage(StorageError, "R2_ACCOUNT_ID"):
            get_storage()

    @override_settings(STORAGE_PROVIDER="dropbox")
    def test_unknown_provider_is_rejected(self):
        with self.assertRaisesMessage(StorageError, "Unknown STORAGE_PROVIDER"):
            get_storage()


@mock_aws
class S3StorageTests(SimpleTestCase):
    def setUp(self):
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=BUCKET)
        self.storage = S3CompatibleStorage(
            bucket=BUCKET, access_key_id="k", secret_access_key="s", region="us-east-1"
        )

    def _read(self, key):
        return self.s3.get_object(Bucket=BUCKET, Key=key)["Body"].read().decode()

    def test_upload_list_and_delete(self):
        self.storage.upload_test_case(7, 1, "1 2\n", "3\n")
        self.storage.upload_test_case(7, 2, "5 5\n", "10\n")
        self.storage.upload_test_case(8, 1, "other\n", "x\n")

        self.assertEqual(
            sorted(self.storage.list_problem_files(7)),
            ["test_cases/7/01", "test_cases/7/01.a", "test_cases/7/02", "test_cases/7/02.a"],
        )
        self.assertEqual(self._read("test_cases/7/02.a"), "10\n")
        self.assertEqual(self.storage.read_file("test_cases/7/01"), "1 2\n")

        self.assertEqual(self.storage.delete_problem_files(7), 4)
        self.assertEqual(self.storage.list_problem_files(7), [])
        # other problems are untouched
        self.assertEqual(len(self.storage.list_problem_files(8)), 2)

    def test_upload_to_missing_bucket_raises(self):
        broken = S3CompatibleStorage(
            bucket="no-such-bucket", access_key_id="k", secret_access_key="s", region="us-east-1"
        )
        with self.assertRaises(StorageError):
            broken.upload_test_case(1, 1, "a", "b")


@mock_aws
@override_settings(CUSTOM_CHECKER_DIR=None)
class MigrateToStorageTests(SimpleTestCase):
    def setUp(self):
        self.s3 = boto3.client("s3", region_name="us-east-1")
        self.s3.create_bucket(Bucket=BUCKET)
        self.storage = S3CompatibleStorage(
            bucket=BUCKET, access_key_id="k", secret_access_key="s", region="us-east-1"
        )
        self.api = PolygonAPI()

    def _keys(self):
        resp = self.s3.list_objects_v2(Bucket=BUCKET)
        return sorted(o["Key"] for o in resp.get("Contents", []))

    def test_uploads_pairs_and_replaces_previous_files(self):
        # leftover file from an earlier migration with more tests
        self.storage.upload_test_case(5, 20, "old", "old")

        tests = [
            {"input": "1\n", "output": "1\n"},
            {"input": "2\n", "output": "4\n"},
            {"input": "3\n", "output": ""},  # no output -> skipped
        ]
        with mock.patch.object(PolygonAPI, "get_test_cases_from_redis", return_value=tests), \
             mock.patch.object(PolygonAPI, "get_custom_checker_info", return_value=None):
            result = self.api.migrate_to_storage("123456", db_problem_id=5, storage=self.storage)

        self.assertEqual(result["uploaded"], 2)
        self.assertEqual(result["skipped"], 1)
        self.assertEqual(result["deleted"], 2)
        self.assertEqual(result["prefix"], "test_cases/5/")
        self.assertEqual(
            self._keys(),
            ["test_cases/5/01", "test_cases/5/01.a", "test_cases/5/02", "test_cases/5/02.a"],
        )

    def test_custom_checker_source_is_uploaded_when_compile_fails(self):
        tests = [{"input": "1\n", "output": "1\n"}]
        with mock.patch.object(PolygonAPI, "get_test_cases_from_redis", return_value=tests), \
             mock.patch.object(PolygonAPI, "get_custom_checker_info", return_value={"name": "chk.cpp"}), \
             mock.patch.object(PolygonAPI, "fetch_custom_checker_file", return_value="int main(){}"), \
             mock.patch.object(PolygonAPI, "compile_custom_checker", return_value=None):
            result = self.api.migrate_to_storage("123456", db_problem_id=9, storage=self.storage)

        self.assertEqual(result["checker_key"], "test_cases/9/custom_checker.cpp")
        self.assertIn("test_cases/9/custom_checker.cpp", self._keys())
