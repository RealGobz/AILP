import os
from dotenv import load_dotenv, find_dotenv
from config import TOP_K
load_dotenv(find_dotenv())

from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from openai import AzureOpenAI


def search_documents(
    question,
    search_client,
    openai_client,
    model_deployment_name="text-embedding-3-small",
    book_id: str = None,
    page_number: int = None,
    grade: str = None,
):
    """Search for documents based on user question with optional filters"""
    print(f"\n[Search] Searching for: '{question}'")
    print("-" * 60)

    # 1. Vectorize query
    response = openai_client.embeddings.create(input=[question], model=model_deployment_name)
    question_vector = response.data[0].embedding

    # 2. Build filters
    filters = []
    if book_id:
        filters.append(f"book_id eq '{book_id}'")
    if page_number:
        filters.append(f"page_number/any(p: p eq {page_number})")
    if grade:
        filters.append(f"grade eq '{grade}'")
    filter_expr = " and ".join(filters) if filters else None

    try:
        results = search_client.search(
            search_text=question,
            vector_queries=[
                {
                    "kind": "vector",
                    "vector": question_vector,
                    "fields": "text_vector",
                    "k": TOP_K,
                }
            ],
            filter=filter_expr,
            query_type="semantic",
            semantic_configuration_name="text_from_book_chunk_semantic",
            select=["header_path", "text", "grade", "page_number", "book_id"],
            include_total_count=True,
        )

        total_count = results.get_count()
        if total_count == 0:
            print("   No results found.\n")
            return []

        print(f"   Found {total_count} result(s):\n")

        results_list = []
        for i, result in enumerate(results, 1):

            results_list.append({
                "score": result.get("@search.score"),
                "reranker_score": result.get("@search.rerankerScore", result.get("@search.reranker_score")),
                "book_id": result.get("book_id"),
                "page_number": result.get("page_number"),
                "header_path": result.get("header_path"),
                "text": result.get("text"),
                "grade": result.get("grade")
            })

        return results_list


    except Exception as e:
        print(f"Search failed: {e}")
        return []


# Alias so both query() and search_documents() can be used
query = search_documents


if __name__ == "__main__":
    search_endpoint = os.getenv("AI_SEARCH_SERVICE_ENDPOINT")
    index_name = os.getenv("INDEX_NAME", "books-index-ailp").strip("\"' ").lower()
    openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    model_deployment_name = os.getenv("EMBEDDING_MODEL_DEPLOYMENT_NAME", "text-embedding-3-small").strip("\"' ")

    credential = DefaultAzureCredential()
    token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

    openai_client = AzureOpenAI(
        azure_endpoint=openai_endpoint,
        azure_ad_token_provider=token_provider,
        api_version="2024-06-01",
    )
    search_client = SearchClient(
        endpoint=search_endpoint,
        index_name=index_name,
        credential=credential,
    )

    sample_question = "What are the core technologies and impact of artificial intelligence?"
    search_documents(sample_question, search_client, openai_client, model_deployment_name)
