import uuid
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv; load_dotenv()
import os
# Configuration
account_name = os.getenv("STORAGE_ACCOUNT_NAME")
account_url = f"https://{account_name}.blob.core.windows.net"
container_name = "books"
books_extracted_container_name = "books-extracted"

# 1. Authenticate with Azure CLI context
# credential = DefaultAzureCredential()
# blob_service_client = BlobServiceClient(account_url, credential=credential)

def upload_book(blob_service_client: BlobServiceClient, file_path: str, grade: int, book_name: str):
    generated_uuid = str(uuid.uuid4())
    grade_string = str(grade)  # Grade as a string of a number

    # 3. Format the required metadata payload
    metadata_payload = {
        "book_id": generated_uuid,
        "book_name": book_name,  # Custom tracking name required by your spec
        "grade": grade_string
    }

    # 4. Use the generated UUID as the explicit filename in the cloud container
    blob_name = f"{generated_uuid}.pdf"
    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    # 5. Upload data with properties
    print(f"Uploading file as cloud asset '{blob_name}'...")
    with open(file_path, "rb") as data:
        blob_client.upload_blob(
            data, 
            overwrite=True, 
            metadata=metadata_payload
        )

    print("Upload successful!")
    return generated_uuid

def upload_book_md(blob_service_client: BlobServiceClient, book_id: str, md_content: str):
    """upload an extracted md file to azure blob storage under the id of the book. the container name is books_extracted"""
    blob_name = f"{book_id}.md"
    blob_client = blob_service_client.get_blob_client(container=books_extracted_container_name, blob=blob_name)
    print(f"Uploading file as cloud asset '{blob_name}'...")
    blob_client.upload_blob(md_content.encode("utf-8"), overwrite=True)
    print("Upload successful!")


if __name__ == "__main__":
    from azure.identity import DefaultAzureCredential

    local_file_path = os.path.join(os.path.dirname(__file__), "..", "tests", "data", "ai.pdf")
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    upload_book(blob_service_client, local_file_path, 1, "test")