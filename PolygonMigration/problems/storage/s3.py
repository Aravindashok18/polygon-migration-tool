"""
S3-compatible storage provider.

One implementation covers both Cloudflare R2 (STORAGE_PROVIDER=r2) and
AWS S3 (STORAGE_PROVIDER=s3). R2 speaks the S3 API; the only differences are
the endpoint URL and the region name, which the factory in __init__.py sets.
"""

import logging

from .base import StorageError, TestCaseStorage

logger = logging.getLogger(__name__)

# S3 DeleteObjects accepts at most 1000 keys per request.
_DELETE_BATCH = 1000


class S3CompatibleStorage(TestCaseStorage):
    def __init__(self, bucket, access_key_id, secret_access_key,
                 region="auto", endpoint_url=None, display_name="S3", scheme="s3"):
        if not bucket:
            raise StorageError("Storage bucket name is not configured.")
        if not access_key_id or not secret_access_key:
            raise StorageError("Storage access key / secret are not configured.")

        import boto3
        from botocore.config import Config

        self.bucket = bucket
        self.display_name = display_name
        self._scheme = scheme
        try:
            self._client = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                aws_access_key_id=access_key_id,
                aws_secret_access_key=secret_access_key,
                region_name=region or None,
                config=Config(retries={"max_attempts": 3, "mode": "standard"}),
            )
        except ValueError as e:  # e.g. malformed endpoint URL / account id
            raise StorageError(f"Invalid storage configuration: {e}") from e

    def location(self):
        return f"{self._scheme}://{self.bucket}"

    def upload_file(self, key, data, content_type="application/octet-stream"):
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            self._client.put_object(
                Bucket=self.bucket, Key=key, Body=data, ContentType=content_type
            )
        except (BotoCoreError, ClientError) as e:
            logger.error("Upload failed for %s/%s: %s", self.location(), key, e)
            raise StorageError(f"Could not upload {key}: {e}") from e
        logger.info("Uploaded %s/%s (%d bytes)", self.location(), key, len(data))

    def list_files(self, prefix):
        from botocore.exceptions import BotoCoreError, ClientError

        keys = []
        try:
            paginator = self._client.get_paginator("list_objects_v2")
            for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
                keys.extend(obj["Key"] for obj in page.get("Contents", []))
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Could not list {prefix}: {e}") from e
        return keys

    def read_file(self, key):
        from botocore.exceptions import BotoCoreError, ClientError

        try:
            obj = self._client.get_object(Bucket=self.bucket, Key=key)
        except (BotoCoreError, ClientError) as e:
            raise StorageError(f"Could not read {key}: {e}") from e
        return obj["Body"].read().decode("utf-8", errors="replace")

    def delete_files(self, keys):
        from botocore.exceptions import BotoCoreError, ClientError

        for start in range(0, len(keys), _DELETE_BATCH):
            batch = keys[start:start + _DELETE_BATCH]
            try:
                resp = self._client.delete_objects(
                    Bucket=self.bucket,
                    Delete={"Objects": [{"Key": k} for k in batch], "Quiet": True},
                )
            except (BotoCoreError, ClientError) as e:
                raise StorageError(f"Could not delete objects: {e}") from e
            errors = resp.get("Errors") or []
            if errors:
                raise StorageError(f"Could not delete {len(errors)} object(s): {errors[0]}")
            logger.info("Deleted %d object(s) from %s", len(batch), self.location())
