from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.config import settings


class StorageError(Exception):
    """Storage backend failed; callers must not leak provider details."""


class StorageObjectNotFound(StorageError):
    """The metadata row exists but the stored object is gone."""


class StorageProvider(ABC):
    """Common interface for S3-compatible object storage (spec #44/#66).

    MinIO, AWS S3, Cloudflare R2 and Alibaba OSS all speak the S3 API, so one
    implementation with configurable endpoint/credentials covers them.
    """

    @abstractmethod
    def put(self, *, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get(self, *, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, *, key: str) -> None: ...


class S3StorageProvider(StorageProvider):
    """boto3-backed adapter. Import stays lazy so tests need no S3 client."""

    def __init__(
        self,
        *,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        region: str,
        use_ssl: bool,
        addressing_style: str = "path",
    ) -> None:
        try:
            import boto3
            from botocore.config import Config
        except ImportError as exc:  # pragma: no cover - deployment dependency
            raise StorageError("boto3 is required for object storage") from exc

        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint or None,
            aws_access_key_id=access_key or None,
            aws_secret_access_key=secret_key or None,
            region_name=region or None,
            use_ssl=use_ssl,
            config=Config(
                signature_version="s3v4",
                s3={"addressing_style": addressing_style},
                connect_timeout=5,
                read_timeout=60,
                retries={"max_attempts": 3, "mode": "standard"},
            ),
        )

    def put(self, *, key: str, data: bytes, content_type: str) -> None:
        try:
            self._client.put_object(
                Bucket=self.bucket,
                Key=key,
                Body=data,
                ContentType=content_type,
                ContentLength=len(data),
            )
        except Exception as exc:  # noqa: BLE001 - normalize provider errors
            raise StorageError("Could not store file") from exc

    def get(self, *, key: str) -> bytes:
        from botocore.exceptions import ClientError

        try:
            response = self._client.get_object(Bucket=self.bucket, Key=key)
            return response["Body"].read()
        except ClientError as exc:
            code = str(exc.response.get("Error", {}).get("Code", ""))
            if code in {"NoSuchKey", "404", "NotFound"}:
                raise StorageObjectNotFound("File is missing from storage") from exc
            raise StorageError("Could not read file") from exc
        except Exception as exc:  # noqa: BLE001
            raise StorageError("Could not read file") from exc

    def delete(self, *, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket, Key=key)
        except Exception as exc:  # noqa: BLE001
            raise StorageError("Could not delete file") from exc


def build_storage_provider() -> StorageProvider:
    return S3StorageProvider(
        endpoint=settings.s3_endpoint,
        access_key=settings.s3_access_key,
        secret_key=settings.s3_secret_key,
        bucket=settings.s3_bucket,
        region=settings.s3_region,
        use_ssl=settings.s3_use_ssl,
        addressing_style=settings.s3_addressing_style,
    )
