from upload_book import upload_book, upload_book_md
from download_book import download_book
from extract_data import extract_data, format_extracted_text
from chunk import chunk_md, get_documents
from typing import Union
from populate_index import populate_index

from azure.storage.blob import BlobServiceClient
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.search.documents import SearchClient
from openai import AzureOpenAI

from dotenv import load_dotenv; load_dotenv()
import os

def pipeline(blob_service_client: BlobServiceClient, document_intelligence_client: DocumentIntelligenceClient, azure_search_client: SearchClient, model_deployment_name: str, openai_client: AzureOpenAI, file_path, grade, book_name, chunk_size: int = 512, overlap: Union[int, float, None] = None, overlap_pct: float = 0.10, tokenizer_model: str = "gpt-4o"):
    

    #upload the book and get the book id
    book_id = upload_book(blob_service_client, file_path, grade, book_name)
    
    #download the book and get the book bytes
    book_bytes = download_book(blob_service_client, book_id)    
    
    #extract the book and get the result
    result = extract_data(document_intelligence_client, book_bytes)
    
    #format the book
    formatted_text = format_extracted_text(result)
    
    #upload the book md
    upload_book_md(blob_service_client, book_id, formatted_text)
    
    #chunk the book
    chunks = chunk_md(formatted_text, chunk_size, overlap, overlap_pct, tokenizer_model)

    #get docs chunks
    docs_chunks = get_documents(chunks, book_id, grade)

    #populate the index
    successful_uploads = populate_index(openai_client, azure_search_client, model_deployment_name, docs_chunks)
    
    return docs_chunks
    




    


    
if __name__ == "__main__":
    from azure.identity import DefaultAzureCredential                           
    from azure.identity import get_bearer_token_provider
    
    account_name = os.getenv("STORAGE_ACCOUNT_NAME")
    account_url = f"https://{account_name}.blob.core.windows.net"
    document_intelligence_endpoint = os.getenv("DOCUMENT_INTELLIGENCE_ENDPOINT")
    openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    azure_search_endpoint = os.getenv("AI_SEARCH_SERVICE_ENDPOINT")
    index_name = os.getenv("INDEX_NAME").strip("\"' ").lower()
    model_deployment_name = os.getenv("EMBEDDING_MODEL_DEPLOYMENT_NAME")
 
    credential = DefaultAzureCredential()
    openai_api_key = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")
    blob_service_client = BlobServiceClient(account_url, credential=credential)
    document_intelligence_client = DocumentIntelligenceClient(document_intelligence_endpoint, credential=credential)
    openai_client = AzureOpenAI(azure_endpoint=openai_endpoint,azure_ad_token_provider=openai_api_key,api_version="2024-06-01")
    azure_search_client = SearchClient(endpoint=azure_search_endpoint, index_name=index_name, credential=credential)

    # Example usage:
    if input("1. populate and set the resources\n 2. query the available index\n enter you choice(1 or 2): ") == "1":
        file_path = os.path.join(os.path.dirname(__file__), "..", "tests", "data", "ai.pdf")
        grade = 10
        book_name = "AI TESTING RAG PIPELINE"
        chunk_size = 128
        overlap = 0.10
        overlap_pct = 0.10
        tokenizer_model = "gpt-4o"

        docs_chunks = pipeline(blob_service_client, document_intelligence_client, azure_search_client, model_deployment_name, openai_client, file_path, grade, book_name, chunk_size, overlap, overlap_pct, tokenizer_model)
        
        """        doc_list.append(
                {
                    "book_id": book_id,
                    "pages": node.metadata.get('page_number'),
                    "header": node.metadata.get('header_path'),
                    "tokens": node.metadata.get('token_count'),
                    "text": node.text
                }
            )
    """
        for doc in docs_chunks:
            
            print(f"BOOK_ID: {doc.get('book_id')}")
            print(f"PAGES: {doc.get('page_number')}")
            print(f"HEADER: {doc.get('header_path')}")
            print(f"TOKEN_COUNT: {doc.get('token_count')}")
            print(f"TEXT: {doc.get('text')}\n")
    else:
        from Agent.Tools.utils.query import query
        sample_question = input("Enter your question: ")
        r = query(sample_question, azure_search_client, openai_client, model_deployment_name)                
        print(r)

    
    



























