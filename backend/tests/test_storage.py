from botocore.exceptions import ClientError

from app.services.storage import S3StorageProvider


class _FakeS3:
    def __init__(self, *, create_error: str | None = None) -> None:
        self.puts: list[dict] = []
        self.buckets: list[dict] = []
        self._fail_first_put = True
        self._create_error = create_error

    def put_object(self, **kwargs):
        if self._fail_first_put:
            self._fail_first_put = False
            raise ClientError({"Error": {"Code": "NoSuchBucket"}}, "PutObject")
        self.puts.append(kwargs)

    def create_bucket(self, **kwargs):
        self.buckets.append(kwargs)
        if self._create_error:
            raise ClientError({"Error": {"Code": self._create_error}}, "CreateBucket")


def _provider(client: _FakeS3, region: str = "us-east-1") -> S3StorageProvider:
    provider = S3StorageProvider.__new__(S3StorageProvider)
    provider.bucket = "azmark"
    provider.region = region
    provider._client = client
    return provider


def test_put_creates_missing_bucket_and_retries():
    client = _FakeS3()
    _provider(client).put(key="k", data=b"x", content_type="text/plain")

    assert client.buckets == [{"Bucket": "azmark"}]
    assert len(client.puts) == 1


def test_put_tolerates_concurrent_bucket_creation():
    client = _FakeS3(create_error="BucketAlreadyOwnedByYou")
    _provider(client, region="eu-west-1").put(key="k", data=b"x", content_type="text/plain")

    assert client.buckets == [
        {
            "Bucket": "azmark",
            "CreateBucketConfiguration": {"LocationConstraint": "eu-west-1"},
        }
    ]
    assert len(client.puts) == 1
