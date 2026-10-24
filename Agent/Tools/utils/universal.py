from azure.storage.blob import BlobServiceClient
from config import CONTAINERS


def validate_book_grade(book_id: str, grade, blob_service_client: BlobServiceClient) -> bool:
    """Check if the book's grade in blob metadata matches the requested grade."""
    try:
        blob_name = book_id if book_id.endswith(".pdf") else f"{book_id}.pdf"
        blob_client = blob_service_client.get_blob_client(container=CONTAINERS[0], blob=blob_name)

        properties = blob_client.get_blob_properties()
        book_grade = properties.metadata.get("grade")

        if str(book_grade).strip() != str(grade).strip():
            return False

        return True
    except Exception:
        return False
