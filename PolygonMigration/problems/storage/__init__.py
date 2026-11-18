"""
Test-case storage package.

Usage:
    from problems.storage import get_storage
    storage = get_storage()          # provider chosen by settings.STORAGE_PROVIDER
    storage.upload_test_case(db_problem_id, 1, input_text, output_text)

Supported STORAGE_PROVIDER values: r2 (default), s3, azure.
Adding a provider = one new module implementing TestCaseStorage + one branch here.
"""

from django.conf import settings

from .base import StorageError, TestCaseStorage

__all__ = ["get_storage", "StorageError", "TestCaseStorage"]


def get_storage():
    provider = (getattr(settings, "STORAGE_PROVIDER", "") or "r2").strip().lower()

    if provider == "r2":
        from .s3 import S3CompatibleStorage

        account_id = settings.R2_ACCOUNT_ID
        if not account_id:
            raise StorageError("R2_ACCOUNT_ID must be set when STORAGE_PROVIDER=r2.")
        endpoint = settings.R2_ENDPOINT_URL or f"https://{account_id}.r2.cloudflarestorage.com"
        return S3CompatibleStorage(
            bucket=settings.R2_BUCKET_NAME,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            region="auto",
            endpoint_url=endpoint,
            display_name="Cloudflare R2",
            scheme="r2",
        )

    if provider == "s3":
        from .s3 import S3CompatibleStorage

        return S3CompatibleStorage(
            bucket=settings.AWS_S3_BUCKET_NAME,
            access_key_id=settings.AWS_ACCESS_KEY_ID,
            secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region=settings.AWS_REGION,
            endpoint_url=settings.AWS_S3_ENDPOINT_URL,
            display_name="AWS S3",
            scheme="s3",
        )

    if provider == "azure":
        from .azure_blob import AzureBlobStorage

        return AzureBlobStorage(
            account_url=settings.AZURE_STORAGE_ACCOUNT_URL,
            tenant_id=settings.AZURE_TENANT_ID,
            client_id=settings.AZURE_CLIENT_ID,
            username=settings.AZURE_USERNAME,
            password=settings.AZURE_PASSWORD,
            container_name=settings.AZURE_CONTAINER_NAME,
        )

    raise StorageError(
        f"Unknown STORAGE_PROVIDER '{provider}'. Use one of: r2, s3, azure."
    )
