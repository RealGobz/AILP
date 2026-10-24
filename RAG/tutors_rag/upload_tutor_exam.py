import uuid
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv; load_dotenv()
import os
# Configuration
account_name = os.getenv("STORAGE_ACCOUNT_NAME")
account_url = f"https://{account_name}.blob.core.windows.net"
tutors_container_name = "tutors"

def upload_tutor_exam(blob_service_client: BlobServiceClient, file_path: str, book_id: str):
    """
    uploads the a tutor's exam paper to the tutor's container
    :param blob_service_client: the blob service client
    :param file_path: the path to the tutor's exam paper
    :param book_id: the id of the book the tutor's exam paper is for
    """
    
    generated_uuid = str(uuid.uuid4())

    blob_name = f"{generated_uuid}_{book_id}.pdf"
    blob_client = blob_service_client.get_blob_client(container=tutors_container_name, blob=blob_name)
    
    print(f"Uploading file as cloud asset '{blob_name}'...")
    with open(file_path, "rb") as data:
        file_data = data.read()
        blob_client.upload_blob(file_data, overwrite=True)



    print("Upload successful!")
    return blob_name[:-4], file_data

def upload_tutor_exam_md(blob_service_client: BlobServiceClient, tutor_exam_id: str, md_content: str):
    """upload an extracted md file to azure blob storage under the id of the book. the container name is books_extracted"""
    blob_name = f"{tutor_exam_id}.md"
    blob_client = blob_service_client.get_blob_client(container=tutors_container_name, blob=blob_name)
    print(f"Uploading file as cloud asset '{blob_name}'...")
    blob_client.upload_blob(md_content.encode("utf-8"), overwrite=True)
    print("Upload successful!")



