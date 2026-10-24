import os
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv; load_dotenv()
from config import CONTAINERS


def list_blobs_with_metadata(container_client: BlobServiceClient):
    """Fetch blobs and their metadata from the container as a list."""
    return list(container_client.list_blobs(include='metadata'))


if __name__ == "__main__":
    storage_account_url = os.getenv("STORAGE_ACCOUNT_URL")
    if not storage_account_url:
        storage_account_name = os.getenv("STORAGE_ACCOUNT_NAME")
        storage_account_url = f"https://{storage_account_name}.blob.core.windows.net"
    elif not storage_account_url.startswith("http"):
        storage_account_url = f"https://{storage_account_url}.blob.core.windows.net"

    container_name = CONTAINERS[0]
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(storage_account_url, credential=credential)
    container_client = blob_service_client.get_container_client(container_name)

    blobs = list_blobs_with_metadata(container_client)
    print(f"Found {len(blobs)} blob(s) in '{container_name}':")
    s = []
    for i,book in enumerate(blobs):
        s.append(
            f"""-=-=-=-=-=
Book number {i} details:
Book Name: {book.metadata["book_name"]}
Book Grade: {book.metadata["grade"]}
book_id: {book.metadata["book_id"]}
-=-=-=-=-=""")    
        print(s[0])

