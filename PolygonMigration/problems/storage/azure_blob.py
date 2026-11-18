"""
Azure Blob Storage provider (STORAGE_PROVIDER=azure).

This is the original AzureBlobManager logic moved behind the TestCaseStorage
interface. It still authenticates with UsernamePasswordCredential, which does
not work for accounts that have MFA enabled.
"""

import logging

from .base import StorageError, TestCaseStorage

logger = logging.getLogger(__name__)


class AzureBlobStorage(TestCaseStorage):
    display_name = "Azure Blob Storage"

    def __init__(self, account_url, tenant_id, client_id, username, password, container_name):
        if not account_url or not container_name:
            raise StorageError("AZURE_STORAGE_ACCOUNT_URL and AZURE_CONTAINER_NAME must be set.")

        from azure.identity import UsernamePasswordCredential
        from azure.storage.blob import BlobServiceClient

        self.container_name = container_name
        credential = UsernamePasswordCredential(
            tenant_id=tenant_id, client_id=client_id, username=username, password=password
        )
        service = BlobServiceClient(account_url=account_url, credential=credential)
        self._container = service.get_container_client(container_name)

    def location(self):
        return f"azure://{self.container_name}"

    def upload_file(self, key, data, content_type="application/octet-stream"):
        from azure.core.exceptions import AzureError
        from azure.storage.blob import ContentSettings

        try:
            self._container.upload_blob(
                name=key, data=data, overwrite=True,
                content_settings=ContentSettings(content_type=content_type),
            )
        except AzureError as e:
            logger.error("Upload failed for %s/%s: %s", self.location(), key, e)
            raise StorageError(f"Could not upload {key}: {e}") from e
        logger.info("Uploaded %s/%s (%d bytes)", self.location(), key, len(data))

    def list_files(self, prefix):
        from azure.core.exceptions import AzureError

        try:
            return [b.name for b in self._container.list_blobs(name_starts_with=prefix)]
        except AzureError as e:
            raise StorageError(f"Could not list {prefix}: {e}") from e

    def read_file(self, key):
        from azure.core.exceptions import AzureError

        try:
            return self._container.download_blob(key).readall().decode("utf-8", errors="replace")
        except AzureError as e:
            raise StorageError(f"Could not read {key}: {e}") from e

    def delete_files(self, keys):
        from azure.core.exceptions import AzureError, ResourceNotFoundError

        for key in keys:
            try:
                self._container.delete_blob(key)
            except ResourceNotFoundError:
                continue
            except AzureError as e:
                raise StorageError(f"Could not delete {key}: {e}") from e
        logger.info("Deleted %d blob(s) from %s", len(keys), self.location())
