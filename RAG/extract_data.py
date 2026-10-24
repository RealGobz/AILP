from azure.ai.documentintelligence import DocumentIntelligenceClient

def extract_data(document_intelligence_client: DocumentIntelligenceClient, file: bytes):
    poller = document_intelligence_client.begin_analyze_document(
        model_id="prebuilt-layout",
        body=file,
        content_type="application/pdf",
        output_content_format="markdown"  
    )
    result = poller.result()
    return result

def format_extracted_text(result) -> str:
    formatted_pages = []
    for page in result.pages:
        page_num = page.page_number
        page_text = "".join(
            result.content[span.offset : span.offset + span.length]
            for span in page.spans
        ).strip()
        formatted_pages.append(
            f"START OF PAGE_NUMBER: {page_num}\n{page_text}\nEND OF PAGE_NUMBER: {page_num}"
        )
    return "\n\n".join(formatted_pages)



if __name__ == "__main__":
    from azure.identity import DefaultAzureCredential
    from dotenv import load_dotenv
    import os
    from azure.storage.blob import BlobServiceClient

    load_dotenv()

    account_name = os.getenv("STORAGE_ACCOUNT_NAME")
    account_url = f"https://{account_name}.blob.core.windows.net"
    endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
    
    credential = DefaultAzureCredential()
    document_intelligence_client = DocumentIntelligenceClient(endpoint=endpoint, credential=credential)
    from download_book import download_book
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    data = download_book(blob_service_client, "03d20e3e-b536-429d-a460-6ecec3cc56fd")
    result = extract_data(document_intelligence_client, data)
    print(format_extracted_text(result))
