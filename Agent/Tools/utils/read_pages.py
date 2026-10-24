from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from dotenv import load_dotenv
import os, re
from config import CONTAINERS, MAX_PAGES_PER_CALL

from Agent.Tools.utils.universal import validate_book_grade

load_dotenv()
storage_url = os.getenv("STORAGE_ACCOUNT_URL")
container_name = CONTAINERS[1]

def extract_pages(md_string: str) -> list[str]:
    pattern = r"(?:START OF PAGE_NUMBER:\s*(\d+)|<!--\s*PAGE\s*(\d+)\s*START\s*-->)\s*\n?(.*?)\s*(?:END OF PAGE_NUMBER:\s*(?:\1|\2)|<!--\s*PAGE\s*(?:\1|\2)\s*END\s*-->)"
    matches = re.findall(pattern, md_string, re.DOTALL)
    if not matches:
        return [md_string.strip()] if md_string.strip() else []

    pages_dict = {}
    for m in matches:
        page_num = int(m[0] or m[1])
        pages_dict[page_num] = m[2].strip()

    max_page = max(pages_dict.keys())
    return [pages_dict.get(i, "") for i in range(1, max_page + 1)]




def read_pages(book_id, pages: tuple[int, int], grade, blob_service_client: BlobServiceClient):

    error_list = []

    if not validate_book_grade(book_id, grade, blob_service_client):
        error_list.append("INVALID BOOK ID")

    if pages[1] - pages[0] > MAX_PAGES_PER_CALL:
        error_list.append(f"You can only read {MAX_PAGES_PER_CALL} pages per call.")

    if error_list:
        return "\n".join(error_list)


    blob_container_client = blob_service_client.get_blob_client(container=container_name, blob=f"{book_id}.md")

    download_stream = blob_container_client.download_blob()
    md_content = download_stream.readall().decode("utf-8")

    pages_extracted = extract_pages(md_content)

    try:
        start_idx = max(pages[0] - 1, 0)
        end_idx = pages[1]
    except Exception as e:
        error_list.append("INVALID PAGE NUMBER")
        return error_list
    
    if error_list:
        return error_list

    return "\n\n".join(pages_extracted[start_idx:end_idx])
    
    
if __name__ == "__main__":
    credential = DefaultAzureCredential()
    blob_service_client = BlobServiceClient(storage_url, credential=credential)
    result = read_pages("02b22af1-f80c-4a6c-9099-f23ccf4bd1fb", (1, 2), "10", blob_service_client)
    if isinstance(result, list):
        print("Errors:", result)
    else:
        print(result)


