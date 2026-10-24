from pydantic import BaseModel, Field
from typing import List
from enum import Enum
from Agent.Tools.utils.query import search_documents
from Agent.Tools.utils.list_blobs import list_blobs_with_metadata
from Agent.Tools.utils.user_gradings import get_user_book_gradings, add_rate_user_topic
from Agent.Tools.utils.read_pages import read_pages as read_pages_helper
from Agent.Tools.utils.read_tutor import describe_tutor
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from openai import AzureOpenAI
import os
from typing import Optional, Union
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
from langchain_core.tools import tool
from azure.storage.blob import BlobServiceClient
from config import CONTAINERS, MAX_PAGES_PER_CALL
from langchain_core.runnables import RunnableConfig
from azure.cosmos import CosmosClient

# Initializing Clients
credential = DefaultAzureCredential()
token_provider = get_bearer_token_provider(credential, "https://cognitiveservices.azure.com/.default")

openai_endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
search_endpoint = os.getenv("AI_SEARCH_SERVICE_ENDPOINT")
index_name = os.getenv("INDEX_NAME", "books-index-ailp")
model_deployment_name = os.getenv("EMBEDDING_MODEL_DEPLOYMENT_NAME", "text-embedding-3-small")
storage_account_url = os.getenv("STORAGE_ACCOUNT_URL")
cosmos_endpoint = os.getenv("COSMOS_ENDPOINT")

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

books_container_client = blob_service_client = BlobServiceClient(storage_account_url, credential=credential)
books_container_client = books_container_client.get_container_client(CONTAINERS[0]) # bad design, never use it again.

cosmos_client = CosmosClient(cosmos_endpoint, credential=credential)



class Citation(BaseModel):
    book_id: Optional[str] = Field(default=None, description="The EXACT ID of the book")
    page_number: Optional[Union[str, int, list[int]]] = Field(default=None, description="The Page Number from that book.")
    grade: Optional[str] = Field(default=None, description="The Grade of the book")




@tool
def respond(response: str, citations: Optional[list[Citation]] = None):
    """You SHOULD always cite your sources. This is the tools you will use to respond to the user.
    the repsonse is your normal repsonse that the user will see. The citations is the sources that the user will use to Double check your answer to them.
    the citations is REQUIRED always unless the user prompt is NOT scientific or study related.

    When to use citation:
        1. User: Explain the ... concept from page ... from the ... book.
        2. User: What is the definition of ...
        3. User: What is the difference between ... and ...
        4. User: What is the ...
        5. User: Explain the ... concept.

    When NOT to use citation:
        1. User: Hi! (Any greetings that arent related to the curriculum unless it really does like an english grammar book or something)
        2. When the Information the User is asking for isnt citable. for instance if the user asks a questoin that you couldnt find the answer for in the curriculum so you used external sources for that or just didnt answer the user.
        3. When it is not study related at all and cant be cited for whatever reason.    
    """
    return "Response delivered."





@tool
def query_curriculum(
    query: str,
    book_id: Optional[str] = None,
    page_number: Optional[int] = None,
    config: RunnableConfig = None,
):
    """Search the curriculum knowledge base using hybrid semantic search.

    Args:
        query: The search query or question to look up.
        book_id: Optional book ID to filter results (e.g., 'Grade_11_CS').
        page_number: Optional page number to filter results.

    Use it When asked about a study or scientific topic that can be found in a book.
    for instance: 
    1. User: Explain the ... concept from page ... from the ... book.
    2. User: What is the definition of ...
    3. User: What is the difference between ... and ...
    4. User: What is the ...
    5. User: Explain the ... concept.
    """
    user_grade = str(config.get("configurable", {}).get("grade", "")).strip() if config else None
    effective_grade = user_grade 

    result = search_documents(
        query,
        search_client,
        openai_client,
        model_deployment_name,
        book_id=book_id,
        page_number=page_number,
        grade=effective_grade,
    )

    formatted_results = []

    for doc in result:
        formatted_results.append(
            f"{doc}\n----------\n"
        )

    return "\n".join(formatted_results)


@tool
def list_books(config: RunnableConfig = None):
    """List all the books' details in the curriculum including the book name, grade, and the book id."""
    user_grade = str(config.get("configurable", {}).get("grade", "")).strip() if config else None
    
    result = list_blobs_with_metadata(books_container_client)
    s = []
    for book in result:
        book_grade = str(book.metadata.get("grade", "")).strip()
        if user_grade and book_grade != user_grade:
            continue
        s.append(
            f"""-=-=-=-=-=
Book number {len(s)} details:
Book Name: {book.metadata.get("book_name")}
Book Grade: {book.metadata.get("grade")}
book_id: {book.metadata.get("book_id")}
-=-=-=-=-="""
        )
    if not s:
        return f"No books found for grade {user_grade}." if user_grade else "No books found in the curriculum."
    return "\n".join(s)

@tool
def read_user_gradings(book_id: str, config: RunnableConfig):
    """Read the user's gradings for a specific book. 
    
    What it does:
        - fetches the user's gradings for a specific book, returning each and every topic you have ever rated the user on in that book.
        - For each topic, it returns the topic name, the rate you gave the user for that topic, and the reason you gave the user for that rate.
    """
    user_id = config["configurable"]["user_id"]
    return get_user_book_gradings(user_id, book_id, cosmos_client)


class Topic(BaseModel):
    topic: str = Field(description="The topic to be graded. It should NOT be a very specific topic (like 'adding 1 + 1'), instead, it should be a little bit general; not too general but somewhere in the middle (not 'Adding numbers' either but 'Adding rational numbers' or 'adding fractions').")
    rate: int = Field(description="The rate of the user's understanding of the topic, from 1 to 10. 1 being 'does not know anything about the topic from the book', and 10 being 'knowing everything they could know from the book'. You should rate the user based on the book's answers not your advanced answers as the user doesnt have to know anything beyond what is in the book.")
    reason: str = Field(description="The reason why you gave the user this rate. it should be a clear and concise explanation of the user's understanding of the topic, and what was AND was NOT met based on the book's content ONLY.")
    
@tool
def rate_user_topics(book_id: str, topics: list[Topic], config: RunnableConfig):
    """Rate the user's topics based on their understanding of the curriculum. Note: The user will NEVER rate themself, you will rate the user.
        - Should only be used after the quiz() tool.
    """
    
    user_id = config["configurable"]["user_id"]
    
    success = add_rate_user_topic(user_id, book_id, topics, cosmos_client)
    if success == False:
        return "Failed to update User Book Gradings. Reason: topic rate is out of range (1-10)."

    return "User Book Gradings updated or/and new topics graded successfully!"


# 1. Define the allowed question types
class QuestionType(str, Enum):
    FIB = "FIB"       # Fill in the blank
    MCQ = "MCQ"       # Multiple Choice
    QA = "QA"         # Short Answer/Open Ended

# 2. Define a single, unified Question model
class Question(BaseModel):
    type: QuestionType = Field(
        description="The type of question: FIB, MCQ, or QA"
    )
    question_text: str = Field(
        description="The actual question. If FIB, use '___' to represent the blank space."
    )
    options: List[str] = Field(
        description="List of choices for MCQ. MUST be an empty list for FIB or QA.", 
        default_factory=list
    )
    correct_answer: str = Field(
        description="The exact correct string answer to grade against."
    )
    explanation: str = Field(
        description="1-2 sentences explaining exactly why this answer is correct."
    )

# 3. The final payload the LLM will output
class Questions(BaseModel):
    questions: List[Question] = Field(
        description="A list of questions testing the student's mastery of the recently covered pages."
    )

@tool
def quiz(questions: List[Question], config: RunnableConfig):
    """Generate a quiz based on the curriculum to test the user's understanding of the topic(s)"""
    return "Questions sent to the user. Tell the user to answer them."


@tool
def read_pages(book_id: str, pages: tuple[int, int], config: RunnableConfig):
    """Read a specific range of pages from a curriculum book.

    Args:
        book_id: The ID of the book to read.
        pages: A tuple of two integers specifying start and end page. Including the start and end pages. (e.g. (1, 3)).

    You can only read up to 5 pages per call.
    """
    grade = config["configurable"]["grade"]

    result = read_pages_helper(book_id, pages, grade, blob_service_client)

    if isinstance(result, list):
        return "Invalid. Reasons: " + '\n'.join(result)
    
    return result


@tool
def read_tutor(book_id: str, config: RunnableConfig):
    """Read the tutor's information for a specific book. 
    
    What it does:
        - fetches the tutor's information for a specific book, returning the tutor's name, question types, exam tricks, and how tricky the tutor is.
    """
    user_id = config["configurable"]["user_id"]
    return describe_tutor(user_id, book_id, cosmos_client)

from langchain_azure_dynamic_sessions import SessionsPythonREPLTool

# Automatically authenticates via DefaultAzureCredential and gives the agent a safe Python REPL
stem_sandbox_tool = SessionsPythonREPLTool(
    name="stem_sandbox_tool",
    description="A safe cloud Python REPL to execute math calculations, scientific equations, formulas, algorithms, and logic code. Input should be valid python code.",
    pool_management_endpoint=os.getenv("AZURE_SESSION_POOL_ENDPOINT")
)


def get_tools(excluded_tools: list[str] = []) -> list:
    """Get all tools."""

    mappings = {
        "query_curriculum": query_curriculum,
        "respond": respond,
        "list_books": list_books,
        "read_user_gradings": read_user_gradings,
        "rate_user_topics": rate_user_topics,
        "quiz": quiz,
        "read_pages": read_pages,
        "read_tutor": read_tutor,
        "stem_sandbox_tool": stem_sandbox_tool
    }
    
    tools = [
        query_curriculum,
        respond,
        list_books,
        read_user_gradings,
        rate_user_topics,
        quiz,
        read_pages,
        read_tutor,
        stem_sandbox_tool
    ]
    
    # Filter out excluded tools
    return [tool for tool in tools if tool.name not in excluded_tools], {k:v for k,v in mappings.items() if k not in excluded_tools}