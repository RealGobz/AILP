import os
import base64
import threading
import concurrent.futures
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv; load_dotenv()
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
from config import CONTAINERS

STORAGE_ACCOUNT_URL = os.getenv("STORAGE_ACCOUNT_URL")
STORAGE_ACCOUNT_NAME = os.getenv("STORAGE_ACCOUNT_NAME")

credential = DefaultAzureCredential()
blob_service_client = BlobServiceClient(STORAGE_ACCOUNT_URL, credential=credential)

# Cache the User Delegation Key in memory so we don't request a new one on every image
_cached_udk = None
_cached_udk_expiry = None
_udk_lock = threading.Lock()

# Thread pool for asynchronous blob uploads
_executor = concurrent.futures.ThreadPoolExecutor(max_workers=5, thread_name_prefix="blob_uploader")
_pending_uploads: list[concurrent.futures.Future] = []
_pending_lock = threading.Lock()


def _get_udk():
    """Retrieves or returns the cached User Delegation Key (thread-safe)."""
    global _cached_udk, _cached_udk_expiry
    now = datetime.now(timezone.utc)
    with _udk_lock:
        if _cached_udk and _cached_udk_expiry and (now < _cached_udk_expiry - timedelta(hours=2)):
            return _cached_udk
        start_time = now - timedelta(minutes=5)
        expiry_time = now + timedelta(days=6)
        _cached_udk = blob_service_client.get_user_delegation_key(key_start_time=start_time, key_expiry_time=expiry_time)
        _cached_udk_expiry = expiry_time
        return _cached_udk


def warmup_storage_auth() -> None:
    """Pre-warms the Azure credential and User Delegation Key in a background daemon thread."""
    def _warmup():
        try:
            _get_udk()
        except Exception as e:
            print(f"[Warning] Storage auth warmup error: {e}")

    threading.Thread(target=_warmup, daemon=True, name="storage_auth_warmup").start()


# Warm up auth at module import so keys are ready before user asks a question
warmup_storage_auth()


def wait_for_image_uploads(timeout: float = 30.0) -> None:
    """Waits for any background image uploads to complete before the LLM accesses the SAS URLs."""
    with _pending_lock:
        futures = list(_pending_uploads)
        _pending_uploads.clear()

    if not futures:
        return

    for fut in futures:
        try:
            fut.result(timeout=timeout)
        except Exception as e:
            print(f"[Warning] Background image upload failed: {e}")


def upload_image_and_get_sas_url(
    img: bytes | str, 
    thread_id: str, 
    message_id: str, 
    user_id: str, 
    idx: int = 0,
    async_upload: bool = True
) -> str:
    """
    Generates a SAS URL instantly and offloads the blob upload to a background thread.
    The resulting SAS URL is immediately usable and lightweight for Cosmos DB (< 1 KB),
    avoiding the 2MB Cosmos DB document limit while removing the 5-second blocking delay.
    """
    # 1. If it's already an http/https URL, return directly
    if isinstance(img, str) and (img.startswith("http://") or img.startswith("https://")):
        return img

    # 2. Extract raw bytes
    if isinstance(img, str):
        if os.path.isfile(img):
            with open(img, "rb") as f:
                raw_bytes = f.read()
        elif img.startswith("data:image/"):
            header, b64_str = img.split(",", 1)
            raw_bytes = base64.b64decode(b64_str)
        else:
            raw_bytes = base64.b64decode(img)
    else:
        raw_bytes = img

    # 3. Detect extension
    if raw_bytes.startswith(b"\x89PNG"):
        ext = "png"
    elif raw_bytes.startswith(b"\xff\xd8\xff"):
        ext = "jpg"
    elif raw_bytes.startswith(b"GIF8"):
        ext = "gif"
    elif raw_bytes.startswith(b"RIFF") and raw_bytes[8:12] == b"WEBP":
        ext = "webp"
    else:
        ext = "png"

    # 4. Blob name: {thread_id}/{message_id}_{idx}.{ext}
    container_name = CONTAINERS[3] # "images"
    blob_name = f"{thread_id}/{message_id}_{idx}.{ext}"
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    # 5. Metadata for traceability
    metadata = {
        "thread_id": str(thread_id),
        "message_id": str(message_id),
        "user_id": str(user_id)
    }

    # 6. Generate User Delegation SAS token (valid 7 days) instantly (offline HMAC calculation)
    start_time = datetime.now(timezone.utc) - timedelta(minutes=5)
    expiry_time = datetime.now(timezone.utc) + timedelta(days=7)
    udk = _get_udk()

    sas_token = generate_blob_sas(
        account_name=STORAGE_ACCOUNT_NAME,
        container_name=container_name,
        blob_name=blob_name,
        user_delegation_key=udk,
        permission=BlobSasPermissions(read=True),
        expiry=expiry_time,
        start=start_time
    )
    sas_url = f"{blob_client.url}?{sas_token}"

    # 7. Upload blob (in background by default, or synchronously if requested)
    if async_upload:
        fut = _executor.submit(blob_client.upload_blob, raw_bytes, metadata=metadata, overwrite=True)
        with _pending_lock:
            _pending_uploads.append(fut)
    else:
        blob_client.upload_blob(raw_bytes, metadata=metadata, overwrite=True)

    return sas_url
