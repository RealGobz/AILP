from langchain_core.messages import SystemMessage
from pydantic import Field
from pydantic import BaseModel
import os
from dotenv import load_dotenv; load_dotenv()
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from azure.identity import DefaultAzureCredential
from config import SYSTEM_PROMPT_FOR_TUTOR_EXTRACTION

azure_project_endpoint = os.getenv("AZURE_PROJECT_ENDPOINT")

class TutorMethod(BaseModel):
    question_types: list[str] = Field(
        description="list of question types the tutor usually asks with percentage of questions for each type, for example 'MCQ: 30%', 'FIB: 20%', 'Q&A: 50%"
    )
    exam_tricks: list[str] = Field(
        description="list of tricks the tutor usually asks"
    )
    how_tricky: str = Field(
        description="how tricky the tutor is, for example 'tricky, student must understand the topic very well to answer'. "
    )



llm = AzureAIOpenAIApiChatModel(
    project_endpoint=azure_project_endpoint,
    model=os.getenv("TUTOR_EXTRACTOR_MODEL_DEPLOYMENT_NAME"),
    credential=DefaultAzureCredential(),
    use_responses_api=False,
)
llm = llm.with_structured_output(TutorMethod)

def extract_tutor_info(test_md: str):
    messages = [SystemMessage(content=SYSTEM_PROMPT_FOR_TUTOR_EXTRACTION.format(content=test_md))]
    response = llm.invoke(messages)
    return response.model_dump()
