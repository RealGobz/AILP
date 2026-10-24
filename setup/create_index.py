import os; from dotenv import load_dotenv; load_dotenv()
from openai import OpenAI
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    SimpleField,
    SearchableField,
    SearchField,
    SearchIndex,
    VectorSearch,
    HnswAlgorithmConfiguration,
    VectorSearchProfile,
    SemanticConfiguration,
    SemanticPrioritizedFields,
    SemanticField,
    SemanticSearch,
)


AI_SEARCH_SERVICE_ENDPOINT = os.getenv("AI_SEARCH_SERVICE_ENDPOINT")
EMBEDDING_MODEL_DEPLOYMENT_NAME = os.getenv("EMBEDDING_MODEL_DEPLOYMENT_NAME")

INDEX_NAME = os.getenv("INDEX_NAME" ).strip("\"' ").lower()

AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")

credential = DefaultAzureCredential()



def create_index():
    print(f"📋 Creating index '{INDEX_NAME}'...")

    # Define the index schema
    fields = [
        SimpleField(name="id", type="Edm.String", key=True),

        SimpleField(name="book_id", type="Edm.String", filterable=True),
        SimpleField(name="page_number", type="Collection(Edm.Int32)", filterable=True), 
        SimpleField(name="token_count", type="Edm.Int32"),
        SearchableField(name="header_path", type="Edm.String"),
        SearchableField(name="text", type="Edm.String"),
        SimpleField(name="grade", type="Edm.String", filterable=True),

        # NEW: Vector field
        SearchField(
            name="text_vector",
            type="Collection(Edm.Single)",
            vector_search_dimensions=1536,  # For text-embedding-3-small
            vector_search_profile_name="text_from_book_chunk_vector",
        ),
    ]

    # Configure the vector search algorithm
    # This example uses HNSW (Hierarchical Navigable Small World) algorithm for efficient vector similarity search.
    # You can choose other algorithms like IVF or PQ based on your requirements and index size.
    # The vector search profile specifies which algorithm configuration to use for vector search queries.
    vector_search = VectorSearch(
        algorithms=[HnswAlgorithmConfiguration(name="my_hnsw_config")],
        profiles=[
            VectorSearchProfile(
                name="text_from_book_chunk_vector", algorithm_configuration_name="my_hnsw_config"
            )
        ],
    )

    semantic_config = SemanticConfiguration(
        name="text_from_book_chunk_semantic",
        prioritized_fields=SemanticPrioritizedFields(
            title_field=SemanticField(field_name="header_path"),
            content_fields=[SemanticField(field_name="text")],
        ),
    )
    semantic_search = SemanticSearch(
        configurations=[semantic_config]
    )

    # Create the index with the new vector configuration and semantic configuration
    index = SearchIndex(
        name=INDEX_NAME,
        fields=fields,
        vector_search=vector_search,
        semantic_search=semantic_search,
    )

    # Create the index client
    index_client = SearchIndexClient(AI_SEARCH_SERVICE_ENDPOINT, credential)

    # Check if the index already exists
    try:
        index_client.get_index(INDEX_NAME)
        print(f"ℹ️ Index '{INDEX_NAME}' already exists. Skipping creation.")
        return False
    except Exception:
        # If not found, create the index
        try:
            index_client.create_index(index)
            print(f"✓ Index '{INDEX_NAME}' created successfully")
            return True
        except Exception as e:
            print(f"✗ Failed to create index: {e}")
            return False


if __name__ == "__main__":
    create_index()