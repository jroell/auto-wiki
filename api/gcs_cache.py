import os
from typing import Optional

CACHE_BUCKET_ENV = "CACHE_BUCKET"
CACHE_PREFIX_ENV = "CACHE_PREFIX"


def get_gcs_client():
    try:
        from google.cloud import storage  # type: ignore
    except Exception as e:
        raise ImportError("google-cloud-storage is required for GCS caching. Install with pip install google-cloud-storage") from e
    return storage.Client()


def gcs_copy(local_path: str, bucket: str, object_name: str):
    client = get_gcs_client()
    b = client.bucket(bucket)
    blob = b.blob(object_name)
    blob.upload_from_filename(local_path)


def gcs_download(bucket: str, object_name: str, local_path: str):
    client = get_gcs_client()
    b = client.bucket(bucket)
    blob = b.blob(object_name)
    blob.download_to_filename(local_path)


def gcs_exists(bucket: str, object_name: str) -> bool:
    client = get_gcs_client()
    b = client.bucket(bucket)
    blob = b.blob(object_name)
    return blob.exists()


def resolve_cache_bucket(config_bucket: Optional[str] = None) -> Optional[str]:
    return config_bucket or os.getenv(CACHE_BUCKET_ENV)


def resolve_cache_prefix(config_prefix: Optional[str] = None, default: str = "adalflow/repos") -> str:
    return os.getenv(CACHE_PREFIX_ENV, config_prefix or default)
