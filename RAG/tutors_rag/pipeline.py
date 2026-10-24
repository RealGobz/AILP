import os
from azure.cosmos import CosmosClient
from RAG.tutors_rag.upload_tutor_exam import upload_tutor_exam_md, upload_tutor_exam
from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from dotenv import load_dotenv
from RAG.extract_data import extract_data, format_extracted_text
from RAG.tutors_rag.extract_tutor import extract_tutor_info
load_dotenv()


def saving_pipeline(blob_service_client: BlobServiceClient, document_intelligence_client: DocumentIntelligenceClient, file_path: str, book_id: str):

    tutor_exam_file_name, file_bytes = upload_tutor_exam(blob_service_client, file_path, book_id) 
    
    extracted_data = extract_data(document_intelligence_client, file_bytes)
    formatted_text = format_extracted_text(extracted_data)
    upload_tutor_exam_md(blob_service_client, tutor_exam_file_name, formatted_text)
    tutor_info = extract_tutor_info(formatted_text)

    return tutor_info, tutor_exam_file_name

def injecting_pipeline(tutor_name: str, tutor_info: dict, exam_blob_name: str, cosmos_client: CosmosClient, user_id: str = "1"):
    db_name = os.getenv("COSMOS_DATABASE_NAME")
    cont_name = os.getenv("COSMOS_USER_GRADINGS_CONTAINER_NAME")

    database = cosmos_client.get_database_client(db_name)
    container = database.get_container_client(cont_name)

    try:
        item = container.read_item(item=str(user_id), partition_key=str(user_id))
    except Exception:
        item = {
            "id": str(user_id),
            "userId": str(user_id),
            "name": str(user_id),
            "grades": {},
            "tutors": {}
        }

    book_id = exam_blob_name.split("_", 1)[1] if "_" in exam_blob_name else exam_blob_name

    if "tutors" not in item:
        item["tutors"] = {}
    if book_id not in item["tutors"]:
        item["tutors"][book_id] = {}

    item["tutors"][book_id][tutor_name] = {
        "data": tutor_info,
        "exam_name": exam_blob_name
    }

    return container.upsert_item(body=item)


if __name__ == "__main__":
    import os
    from azure.identity import DefaultAzureCredential
    from Agent.Tools.tools import credential

    account_name = os.getenv("STORAGE_ACCOUNT_NAME")
    account_url = f"https://{account_name}.blob.core.windows.net"
    document_intelligence_endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
    openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    document_intelligence_client = DocumentIntelligenceClient(document_intelligence_endpoint, credential=credential)
    cosmos_client = CosmosClient(os.getenv("COSMOS_ENDPOINT"), credential=credential)

    tutor_info, exam_blob_name = saving_pipeline(blob_service_client, document_intelligence_client, "./tests/data/test_exam.pdf", "tutor-exams")
    result = injecting_pipeline("test tutor", tutor_info, exam_blob_name, cosmos_client, user_id="1")


    