import os
from urllib.parse import urlparse
import boto3

BUCKET = os.getenv("MINIO_BUCKET", "attest-documents")


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


def read_object(key: str) -> bytes:
    return client().get_object(Bucket=BUCKET, Key=key)["Body"].read()

