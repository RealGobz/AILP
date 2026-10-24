import os
import requests
from dotenv import load_dotenv
from azure.identity import DefaultAzureCredential

from config import PII_CATEGORIES

load_dotenv()

credential = DefaultAzureCredential()
endpoint = os.getenv("AZURE_OPENAI_ENDPOINT", "").rstrip("/")


def _chunk_text(text: str, max_chunk_size: int = 4500) -> list[str]:
    """Splits long text into chunks smaller than Azure Language Service's 5,120 character limit."""
    if len(text) <= max_chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
        # Prefer breaking on newlines or spaces
        split_idx = text.rfind("\n", start, end)
        if split_idx == -1 or split_idx <= start:
            split_idx = text.rfind(" ", start, end)
        if split_idx == -1 or split_idx <= start:
            split_idx = end
        chunks.append(text[start:split_idx])
        start = split_idx
    return chunks


def redact_pii(text: str, language: str = None, categories: list[str] = None) -> tuple[str, list[dict]]:
    """
    Detects and masks PII in text using Azure AI Language Service.
    Automatically detects language (Arabic, Spanish, English, etc.) if not specified.
    Handles long text (such as image transcriptions) by chunking.
    Uses categories configured in config.py by default.
    Returns: (redacted_text, detected_entities)
    """
    if not text.strip():
        return text, []

    if categories is None:
        categories = PII_CATEGORIES

    try:
        token = credential.get_token("https://cognitiveservices.azure.com/.default").token
        url = f"{endpoint}/language/:analyze-text?api-version=2023-04-01"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        chunks = _chunk_text(text)
        documents = []
        for i, chunk in enumerate(chunks):
            doc = {"id": str(i), "text": chunk}
            if language:
                doc["language"] = language
            documents.append(doc)

        parameters = {"modelVersion": "latest"}
        if categories:
            parameters["piiCategories"] = categories

        body = {
            "kind": "PiiEntityRecognition",
            "parameters": parameters,
            "analysisInput": {
                "documents": documents
            }
        }

        response = requests.post(url, headers=headers, json=body, timeout=10)
        response.raise_for_status()
        
        results = response.json().get("results", {})
        returned_docs = results.get("documents", [])
        
        if not returned_docs:
            errors = results.get("errors", [])
            if errors:
                print(f"PII API returned error: {errors}")
            return text, []

        # Sort returned documents by original chunk id
        returned_docs = sorted(returned_docs, key=lambda d: int(d.get("id", 0)))
        
        redacted_text = "".join(d.get("redactedText", "") for d in returned_docs)
        all_entities = []
        for d in returned_docs:
            all_entities.extend(d.get("entities", []))

        return redacted_text, all_entities

    except Exception as e:
        print(f"PII redaction error: {e}")
        return text, []
