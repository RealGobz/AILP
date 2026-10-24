from azure.ai.projects.models import UserConversationSimulationUserBehaviorConfiguration
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv; load_dotenv()
import os
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential

def create_user_gradings_entry(user_id, grade, cosmos_client: CosmosClient, blob_service_container_client):

    try:
        blobs = list(blob_service_container_client.list_blobs(include='metadata'))
    except TypeError:
        blobs = list(blob_service_container_client.list_blobs())

    grades = {}
    for blob in blobs:
        metadata = getattr(blob, "metadata", {}) or {}
        if grade and metadata.get("grade"):
            if str(metadata.get("grade")).strip() != str(grade).strip():
                continue
        b_name = getattr(blob, "name", str(blob))
        book_id = metadata.get("book_id") or b_name.removesuffix(".pdf")
        grades[book_id] = {}

    db_name = os.getenv("COSMOS_DATABASE_NAME")
    cont_name = os.getenv("COSMOS_USER_GRADINGS_CONTAINER_NAME")

    database = cosmos_client.get_database_client(db_name)
    container = database.get_container_client(cont_name)

    # create an entry in the UserGradings container for the user
    new_item = {
        "id": str(user_id),
        "userId": str(user_id),
        "name": str(user_id),
        "grades": grades
    }

    return container.upsert_item(body=new_item)

def get_user_book_gradings(user_id, book_id, cosmos_client: CosmosClient):

    db_name = os.getenv("COSMOS_DATABASE_NAME")
    cont_name = os.getenv("COSMOS_USER_GRADINGS_CONTAINER_NAME")

    database = cosmos_client.get_database_client(db_name)
    container = database.get_container_client(cont_name)

    # get the UserGradings entry for the user_id and return the grades dictionary
    try:
        item = container.read_item(item=str(user_id), partition_key=str(user_id))
        return item.get("grades", {})
    except ResourceNotFoundError:
        credential = DefaultAzureCredential()
        storage_url = os.getenv("STORAGE_ACCOUNT_URL")
        blob_service_client = BlobServiceClient(storage_url, credential=credential)
        blob_container_client = blob_service_client.get_container_client("books")
        created_item = create_user_gradings_entry(user_id, None, cosmos_client, blob_container_client)
        return created_item.get("grades", {}) if isinstance(created_item, dict) else {}
    except Exception:
        try:
            query = "SELECT * FROM c WHERE c.id = @user_id"
            params = [{"name": "@user_id", "value": str(user_id)}]
            items = list(container.query_items(query=query, parameters=params, enable_cross_partition_query=True))
            if items:
                return items[0].get("grades", {})
        except Exception:
            pass
        return {}


def add_rate_user_topic(user_id, book_id, topics, cosmos_client: CosmosClient):
    db_name = os.getenv("COSMOS_DATABASE_NAME")
    cont_name = os.getenv("COSMOS_USER_GRADINGS_CONTAINER_NAME")

    database = cosmos_client.get_database_client(db_name)
    container = database.get_container_client(cont_name)

    item = container.read_item(item=str(user_id), partition_key=str(user_id))

    if "grades" not in item:
        item["grades"] = {}
    if book_id not in item["grades"]:
        item["grades"][book_id] = {}

    for topic in topics:
        if hasattr(topic, "model_dump"):
            topic = topic.model_dump()
        topic_name = topic.get("topic")
        topic_rate = topic.get("rate")
        if topic_rate > 10 or topic_rate < 0:
            return False
        topic_reason = topic.get("reason")

        item["grades"][book_id][topic_name] = {
            "rate": topic_rate,
            "reason": topic_reason
        }

    return container.upsert_item(body=item)
 
 
if __name__ == "__main__":
    credential = DefaultAzureCredential()
    storage_url = os.getenv("STORAGE_ACCOUNT_URL")
    cosmos_url = os.getenv("COSMOS_ENDPOINT")
    blob_service_client = BlobServiceClient(storage_url, credential=credential)
    blob_container_client = blob_service_client.get_container_client("books")
    cosmos_client = CosmosClient(cosmos_url, credential=credential)
    created_item = create_user_gradings_entry("test_user", "10", cosmos_client, blob_container_client)
    print(created_item.get("grades", {}) if isinstance(created_item, dict) else {})