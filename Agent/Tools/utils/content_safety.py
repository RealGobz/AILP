import os
from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.contentsafety.models import AnalyzeTextOptions
from config import CONTENT_SAFETY_SEVERITY_LEVELS
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

load_dotenv()

content_safety_endpoint = os.getenv("CONTENT_SAFETY_ENDPOINT")
credential = DefaultAzureCredential()
client = ContentSafetyClient(content_safety_endpoint, credential)



def _chunk_text(text: str, max_chunk_size: int = 9000) -> list[str]:
    """Splits long text into chunks smaller than Azure Content Safety's 10,000 character limit."""
    if len(text) <= max_chunk_size:
        return [text]
    print("Splitting text into chunks")
    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chunk_size
        if end >= len(text):
            chunks.append(text[start:])
            break
        split_idx = text.rfind("\n", start, end)
        if split_idx == -1 or split_idx <= start:
            split_idx = text.rfind(" ", start, end)
        if split_idx == -1 or split_idx <= start:
            split_idx = end
        chunks.append(text[start:split_idx])
        start = split_idx
    return chunks


def guardrails(text: str):
    try:
        chunks = _chunk_text(text)
        max_severity_levels = {}

        for chunk in chunks:
            request_options = AnalyzeTextOptions(text=chunk)
            response = client.analyze_text(request_options)
            for item in response.categories_analysis:
                max_severity_levels[item.category] = max(
                    max_severity_levels.get(item.category, 0), item.severity
                )

        flags = []
        for category, score in max_severity_levels.items():
            if score >= CONTENT_SAFETY_SEVERITY_LEVELS.get(category, 2):
                flags.append(f"This message was flagged for {category} with severity score {score}")

        if flags:
            return flags, max_severity_levels

        return False, max_severity_levels

    except Exception as e:
        print(f"Error in content safety: {e}")
        return False, None


        
