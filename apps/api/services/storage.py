import os
from pathlib import Path

import boto3

BUCKET = os.getenv("MINIO_BUCKET", "attest-documents")
# "local" stores files on disk (no MinIO needed for development); "s3" uses MinIO/S3.
STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local")
LOCAL_STORAGE_DIR = Path(os.getenv("LOCAL_STORAGE_DIR", "storage/api-uploads"))


def client():
    endpoint = os.getenv("MINIO_ENDPOINT", "localhost:9000")
    if not endpoint.startswith("http"):
        scheme = "https" if os.getenv("MINIO_SECURE", "false").lower() == "true" else "http"
        endpoint = f"{scheme}://{endpoint}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("MINIO_ACCESS_KEY", "attest"),
        aws_secret_access_key=os.getenv("MINIO_SECRET_KEY", "attestsecret"),
        region_name="us-east-1",
    )


def ensure_bucket() -> None:
    s3 = client()
    buckets = [b["Name"] for b in s3.list_buckets().get("Buckets", [])]
    if BUCKET not in buckets:
        s3.create_bucket(Bucket=BUCKET)


def presigned_put(key: str, content_type: str) -> str:
    ensure_bucket()
    return client().generate_presigned_url(
        "put_object",
        Params={"Bucket": BUCKET, "Key": key, "ContentType": content_type},
        ExpiresIn=900,
    )


def _local_path(key: str) -> Path:
    path = (LOCAL_STORAGE_DIR / key).resolve()
    if LOCAL_STORAGE_DIR.resolve() not in path.parents:
        raise ValueError("Invalid storage key")
    return path


def put_object(key: str, data: bytes, content_type: str) -> None:
    if STORAGE_BACKEND == "local":
        path = _local_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return
    ensure_bucket()
    client().put_object(Bucket=BUCKET, Key=key, Body=data, ContentType=content_type)


def read_object(key: str) -> bytes:
    if STORAGE_BACKEND == "local":
        return _local_path(key).read_bytes()
    return client().get_object(Bucket=BUCKET, Key=key)["Body"].read()
