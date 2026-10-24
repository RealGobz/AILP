import uuid
from azure.search.documents import SearchClient


def generate_batch_embeddings(texts: list[str], openai_client, model_deployment_name: str) -> list[list[float]]:
    """Generate vector embeddings for a list of texts in a single batch call."""
    response = openai_client.embeddings.create(
        input=texts,
        model=model_deployment_name
    )
    # Ensure embeddings match the original order
    return [item.embedding for item in sorted(response.data, key=lambda x: x.index)]


def populate_index(openai_client, search_client: SearchClient, model_deployment_name: str, chunks: list[dict]) -> float:
    """Populate the Azure AI Search index with chunked documents. And returns a percentage of successful uploads"""
    
    if not chunks:
        print("⚠️ No chunks provided to index.")
        return 0.0

    # 1. Generate embeddings in a single batch
    texts = [chunk.get("text", "") for chunk in chunks]
    embeddings = generate_batch_embeddings(texts, openai_client, model_deployment_name)

    # 2. Build Azure AI Search document payloads
    docs_list = []
    for chunk, embedding in zip(chunks, embeddings):
        docs_list.append(
            {
                "id": str(uuid.uuid4()),
                "book_id": chunk.get("book_id"),
                "page_number": chunk.get("page_number"),
                "header_path": chunk.get("header_path"),
                "token_count": chunk.get("token_count"),
                "text": chunk.get("text"),
                "text_vector": embedding,  # Matches SearchField(name="text_vector")
                "grade": str(chunk.get("grade")),
            }
        )

    # 3. Upload to Azure AI Search
    result = search_client.upload_documents(documents=docs_list)
    uploaded_count = sum(1 for r in result if r.succeeded)
    print(f"✓ Uploaded {uploaded_count}/{len(docs_list)} chunks successfully")
    return sum(1 for r in result if r.succeeded) / len(docs_list)
