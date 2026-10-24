from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import ResourceExistsError
from dotenv import load_dotenv; load_dotenv()
import os
from config import CONTAINERS

account_name = os.getenv("STORAGE_ACCOUNT_NAME")
account_url = f"https://{account_name}.blob.core.windows.net"

# 1. Initialize the DefaultAzureCredential
credential = DefaultAzureCredential()

# 2. Build the BlobServiceClient using token credentials
blob_service_client = BlobServiceClient(account_url, credential=credential)


# 3. Create the containers safely
for container_name in CONTAINERS:
    try:
        print(f"Creating container '{container_name}'...")
        container_client = blob_service_client.create_container(container_name)
        print(f"Container '{container_name}' created successfully!")
    except ResourceExistsError:
        print(f"Container '{container_name}' already exists.")
