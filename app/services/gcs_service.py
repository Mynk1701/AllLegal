"""
GCS service — signed PDF URLs, replacing Supabase Storage.

Talks to GCS via its S3-compatible XML API using HMAC interoperability
creds, not the google-cloud-storage SDK. Auth is a user-account HMAC key
(Cloud Storage -> Settings -> Interoperability -> "Access keys for your
user account"), not a service-account key: an org policy on the GCP
project (iam.disableServiceAccountKeyCreation) blocks service-account
keys, including HMAC ones, for this project. See HANDOVER.md.
"""
import logging
from typing import Optional

import boto3
from botocore.config import Config

from app.core.config import settings

logger = logging.getLogger(__name__)

GCS_ENDPOINT = "https://storage.googleapis.com"


class GCSService:
    """Wraps a boto3 S3 client pointed at GCS for signed PDF URLs."""

    def __init__(self):
        self.client = boto3.client(
            "s3",
            endpoint_url=GCS_ENDPOINT,
            aws_access_key_id=settings.GCS_HMAC_ACCESS_KEY,
            aws_secret_access_key=settings.GCS_HMAC_SECRET_KEY,
            # botocore >=1.36 defaults to attaching an AWS-specific flexible
            # checksum, which GCS's S3-compatible XML API doesn't recognize
            # the same way -> SignatureDoesNotMatch. Restore the old
            # "only when required" behavior so signatures match.
            config=Config(
                signature_version="s3v4",
                request_checksum_calculation="when_required",
                response_checksum_validation="when_required",
            ),
        )

    def get_pdf_signed_url(self, case_id: str, expiry: Optional[int] = None) -> Optional[str]:
        """Signed URL for <GCS_BUCKET>/<case_id>.pdf (Option 1 — name-by-case_id)."""
        key = settings.PDF_PATH_TEMPLATE.format(case_id=case_id)
        try:
            return self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": settings.GCS_BUCKET, "Key": key},
                ExpiresIn=expiry or settings.PDF_SIGNED_URL_EXPIRY,
            )
        except Exception as e:
            logger.warning(f"⚠️ GCS signed URL failed for {case_id}: {str(e)}")
            return None


gcs_service = GCSService()
