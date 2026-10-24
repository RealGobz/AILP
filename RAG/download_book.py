from azure.storage.blob import BlobServiceClient


def download_book(blob_service_client: BlobServiceClient, book_id: str, container_name: str = "books") -> bytes:
    download_stream = blob_service_client.get_container_client(container_name).get_blob_client(f"{book_id}.pdf").download_blob()
    return download_stream.readall()
    
if __name__ == "__main__":
    from azure.identity import DefaultAzureCredential
    from dotenv import load_dotenv
    import os
    load_dotenv()
    account_name = os.getenv("STORAGE_ACCOUNT_NAME")
    account_url = f"https://{account_name}.blob.core.windows.net"
    container_name = "books"
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    data = download_book(blob_service_client, "03d20e3e-b536-429d-a460-6ecec3cc56fd")
    
    print(f"the length of data is: {len(data)}")