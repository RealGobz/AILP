# from langgraph.store.memory import InMemoryStore
from langchain_core.messages import HumanMessage
from langgraph.store.base import BaseStore
from langgraph.constants import END
from langchain_core.messages import ToolMessage, SystemMessage
import os
import sys
import json
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
from dotenv import load_dotenv; load_dotenv()
from azure.identity import DefaultAzureCredential
from langchain_azure_ai.chat_models import AzureAIOpenAIApiChatModel
from langgraph.graph import StateGraph, MessagesState
from config import SYSTEM_PROMPT, CURRENT_MESSAGES_COUNT_THRESHOLD, LTM_AGENT_SYSTEM_PROMPT, SYSTEM_PROMPT_WHEN_EXAM_PREP, MAX_IMAGES_PER_REQUEST, AGENT_TEMPERATURE, LTM_AGENT_TEMPERATURE
from Agent.Tools.tools import get_tools
# from langgraph.checkpoint.memory import MemorySaver
from langchain_core.runnables import RunnableConfig
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field
from langchain_azure_cosmosdb import CosmosDBStore, CosmosDBSaverSync
# import base64
# from Agent.Tools.utils.content_safety import guardrails as check_guardrails
from Agent.Tools.utils.pii import redact_pii
from Agent.Tools.utils.analyze_images import upload_image_and_get_sas_url, wait_for_image_uploads
from Agent.Tools.utils.latency_tracker import latency_tracker
from azure.monitor.opentelemetry import configure_azure_monitor
from opentelemetry import trace

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Custom State
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

class AgentState(MessagesState):
    preferences: list[str]
    study_preferences: list[str]
    current_messages_count: int


# -=-=-=-=-=-=-=-=-=-=-=
# Custom Schemas 
# -=-=-=-=-=-=-=-=-=-=-=

class LTM_Agent_Schema(BaseModel):
    new_preferences: list[str] = Field(
        description="New general personal facts discovered about the user. Empty list if none.", 
        default_factory=list
    )
    new_study_preferences: list[str] = Field(
        description="New specific ways the user prefers to learn or study. Empty list if none.", 
        default_factory=list
    )


# -=-=-=-=-=-=-=-=-=-=-=
# Agents & Clients Definitions
# -=-=-=-=-=-=-=-=-=-=-=

llm_deployment = os.getenv("AGENT_MODEL_DEPLOYMENT_NAME")
ltm_llm_deployment = os.getenv("LTM_AGENT_MODEL_DEPLOYMENT_NAME")
azure_project_endpoint = os.getenv("AZURE_PROJECT_ENDPOINT")

COSMOS_ENDPOINT = os.getenv("COSMOS_ENDPOINT")
COSMOS_DATABASE_NAME = os.environ.get("COSMOS_DATABASE_NAME")
COSMOS_CONTAINER_NAME = os.environ.get("COSMOS_CONTAINER_NAME")
COSMOS_CHECKPOINTS_CONTAINER_NAME = os.environ.get("COSMOS_CHECKPOINTS_CONTAINER_NAME")

credential = DefaultAzureCredential()

configure_azure_monitor()
tracer = trace.get_tracer("ailp.agent")

#main agent
llm = AzureAIOpenAIApiChatModel(
    project_endpoint=azure_project_endpoint,
    model=llm_deployment,
    credential=credential,
    use_responses_api=False,
    # temperature=AGENT_TEMPERATURE
)
tools, tools_map = get_tools()
agent = llm.bind_tools(tools)

#LTM agent
ltm_llm = AzureAIOpenAIApiChatModel(
    project_endpoint=azure_project_endpoint,
    model=ltm_llm_deployment,
    credential=credential,
    use_responses_api=False,
    # temperature=LTM_AGENT_TEMPERATURE
)
ltm_agent = ltm_llm.with_structured_output(LTM_Agent_Schema, method="json_mode")




@latency_tracker.track()
def images(state: AgentState, config: RunnableConfig):
    with tracer.start_as_current_span("images") as span:
        span.set_attribute("user_id", config["configurable"]["user_id"])
        span.set_attribute("gen_ai.conversation.id", config["configurable"]["thread_id"])

        # Consume images so they are not re-processed across subsequent turns
        configurable = config.get("configurable", {})
        img_list = configurable.pop("images", [])

        if not img_list:
            return

        # Enforce maximum images per request
        img_list = img_list[:MAX_IMAGES_PER_REQUEST]

        last_message = state["messages"][-1]
        message_id = last_message.id
        user_text = str(last_message.content or "").strip()
        user_id = config.get("configurable", {}).get("user_id")
        thread_id = config.get("configurable", {}).get("thread_id")

        content_blocks = []
        if user_text:
            content_blocks.append({"type": "text", "text": user_text})

        
        for idx, img in enumerate(img_list[:MAX_IMAGES_PER_REQUEST]):
            sas_url = upload_image_and_get_sas_url(
                img=img,
                thread_id=thread_id,
                message_id=message_id,
                user_id=user_id,
                idx=idx
            )
            content_blocks.append({
                "type": "image_url",
                "image_url": {"url": sas_url}
            })


    if not any(block.get("type") == "text" for block in content_blocks):
        content_blocks.insert(0, {"type": "text", "text": "Analyze the attached image(s)."})

    message = HumanMessage(
        content=content_blocks,
        id=message_id
    )

    return {"messages": [message]}

    

@latency_tracker.track()
def pii_redaction(state: AgentState, config: RunnableConfig):
    """Redacts PII from incoming human messages so Cosmos DB only stores masked information."""

    with tracer.start_as_current_span("pii_redaction") as span:
        span.set_attribute("user_id", config["configurable"]["user_id"])
        span.set_attribute("gen_ai.conversation.id", config["configurable"]["thread_id"])
        
        if not state.get("messages"):
            return

        message = state["messages"][-1] 

        if isinstance(message, HumanMessage):
            if isinstance(message.content, list):
                # Multimodal message: redact only the text blocks, leave image URLs untouched
                text_parts = [part.get("text", "") for part in message.content if part.get("type") == "text"]
                combined_text = "\n".join(text_parts)
                cleaned_text, _ = redact_pii(combined_text)
                for part in message.content:
                    if part.get("type") == "text":
                        part["text"] = cleaned_text
            else:
                cleaned_text, _ = redact_pii(str(message.content))
                message.content = cleaned_text

        return {"messages": [message]}    


@latency_tracker.track()
def increase_current_messages_count(state: AgentState, config: RunnableConfig):
    count = state.get("current_messages_count", 0) + 1
    return {"current_messages_count": count}

@latency_tracker.track()
def retrieve_ltm(state: AgentState, config: RunnableConfig, store: BaseStore):
    with tracer.start_as_current_span("retrieve_ltm") as span:
        span.set_attribute("user_id", config["configurable"]["user_id"])
        span.set_attribute("gen_ai.conversation.id", config["configurable"]["thread_id"])

        user_id = config["configurable"]["user_id"]
        
        # 2. Define our targets (Namespace and standard Key)
        pref_namespace = ("preferences", user_id)
        study_namespace = ("study_preferences", user_id)
        fixed_key = "current_list"

        existing_pref_doc = store.get(pref_namespace, fixed_key)
        if existing_pref_doc and "items" in existing_pref_doc.value:
            old_pref_list = existing_pref_doc.value["items"]
        else:
            old_pref_list = []

        existing_study_doc = store.get(study_namespace, fixed_key)
        if existing_study_doc and "items" in existing_study_doc.value:
            old_study_list = existing_study_doc.value["items"]
        else:
            old_study_list = []


        preferences = old_pref_list
        study_preferences = old_study_list
        
        return {"preferences": preferences, "study_preferences": study_preferences}

@latency_tracker.track()
def call_agent(state: AgentState, config: RunnableConfig):
    with tracer.start_as_current_span("call_agent") as span:
        span.set_attribute("user_id", config["configurable"]["user_id"])
        span.set_attribute("gen_ai.conversation.id", config["configurable"]["thread_id"])
    
        preferences = state["preferences"]
        study_preferences = state["study_preferences"]
        configurable = config.get("configurable", {})
        exam_prep = configurable.get("exam_prep", False)

        name = configurable.get("name", "Not specified")
        age = configurable.get("age", "Not specified")
        gender = configurable.get("gender", "Not specified")
        grade = configurable.get("grade", "Not specified")
        language = configurable.get("language", "Not specified")
        country = configurable.get("country", "Not specified")

        system_prompt = SYSTEM_PROMPT.format(
            name=name,
            age=age,
            gender=gender,
            grade=grade,
            language=language,
            country=country,
            preferences=preferences,
            study_preferences=study_preferences
        )

        messages = list(state["messages"])

        if exam_prep == True:
            messages = [SystemMessage(content=system_prompt + SYSTEM_PROMPT_WHEN_EXAM_PREP)] + messages
        else:
            messages = [SystemMessage(content=system_prompt)] + messages

        wait_for_image_uploads()
        response = agent.invoke(messages)

        if response.content:
            span.set_attribute("gen_ai.completion", str(response.content))    

        return {"messages": [response]}

@latency_tracker.track()
def call_ltm_agent(state: AgentState, config: RunnableConfig, store: BaseStore):
    with tracer.start_as_current_span("call_ltm_agent") as span:
        span.set_attribute("user_id", config["configurable"]["user_id"])
        span.set_attribute("gen_ai.conversation.id", config["configurable"]["thread_id"])
    
        if state["current_messages_count"] < CURRENT_MESSAGES_COUNT_THRESHOLD:
            return

        print("\n========================================================================================================================")
        print("\nLTM agent called\n")
        print("========================================================================================================================")
        
        user_id = config["configurable"]["user_id"]
        fixed_key = "current_list"

        preferences = state["preferences"]
        study_preferences = state["study_preferences"]
        pref_namespace = ("preferences", user_id)
        study_namespace = ("study_preferences", user_id)

        user_messages = [m for m in state["messages"] if isinstance(m, HumanMessage)][-CURRENT_MESSAGES_COUNT_THRESHOLD:]
        # Sanitize user messages for Phi-4 (text-only model) by extracting text content
        text_user_messages = []
        for m in user_messages:
            if isinstance(m.content, list):
                plain_text = "".join(part.get("text", "") for part in m.content if part.get("type") == "text")
                text_user_messages.append(HumanMessage(content=plain_text, id=m.id))
            else:
                text_user_messages.append(m)

        messages = [SystemMessage(content=LTM_AGENT_SYSTEM_PROMPT.format(preferences=preferences, study_preferences=study_preferences))] + text_user_messages

        response = ltm_agent.invoke(messages)

        new_prefs = response.new_preferences or []
        new_study = response.new_study_preferences or []

        if new_prefs:
            updated_pref_list = list(set(preferences + new_prefs))
            store.put(namespace=pref_namespace, key=fixed_key, value={"items": updated_pref_list})
        if new_study:
            updated_study_list = list(set(study_preferences + new_study))
            store.put(namespace=study_namespace, key=fixed_key, value={"items": updated_study_list})
        
        return {"current_messages_count": 0}
    
    
def tools_router(state: AgentState):
    """Custom router replacing tools_condition."""
    last_message = state["messages"][-1]
    
    # If the LLM requested tool calls, route to our custom tools node
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools_node"
    
    return END # should never happen

    
    



@latency_tracker.track()
def tools_node(state: AgentState, config: RunnableConfig):
    """Custom node replacing ToolNode. It executes tool calls sequentially."""

    with tracer.start_as_current_span("tools_node") as span:
        span.set_attribute("user_id", config["configurable"]["user_id"])
        span.set_attribute("gen_ai.conversation.id", config["configurable"]["thread_id"])

        last_message = state["messages"][-1]
        tool_outputs = []
        
        # Loop through each tool call requested by the model
        for tool_call in last_message.tool_calls:
            tool_name = tool_call["name"]
            tool_args = tool_call["args"]
            tool_id = tool_call["id"]
            
            # Start an individual child span for this specific tool execution
            with tracer.start_as_current_span(f"tool.{tool_name}") as tool_span:
                tool_span.set_attribute("gen_ai.tool.name", tool_name)
                tool_span.set_attribute("gen_ai.tool.call.id", tool_id)
                tool_span.set_attribute("gen_ai.tool.parameters", json.dumps(tool_args, ensure_ascii=False))
                
                # Execute the tool
                tool_func = tools_map[tool_name]
                result = tool_func.invoke(tool_args, config=config)
                
                # Log the tool output
                tool_span.set_attribute("gen_ai.tool.result", str(result))

                if tool_name == "respond":
                    span.set_attribute("agent_response", str(result))
            
            # Append a formal ToolMessage tracking back to its original call ID
            tool_outputs.append(
                ToolMessage(content=str(result), tool_call_id=tool_id)
            )
            
        return {"messages": tool_outputs}

def route_after_tools(state: AgentState):
    """If respond was called, route to output_guardrails; otherwise continue agent loop."""
    for msg in reversed(state["messages"]):
        if hasattr(msg, "tool_calls") and msg.tool_calls:
            for tc in msg.tool_calls:
                if tc["name"] == "respond":
                    return END
            break
    return "call_agent"

# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=
# Graph Builder
# -=-=-=-=-=-=-=-=-=-=-=-=-=-=-=

workflow = StateGraph(AgentState)

workflow.add_node("images", images)
workflow.add_node("pii_redaction", pii_redaction)
workflow.add_node("increase_current_messages_count", increase_current_messages_count)
workflow.add_node("retrieve_ltm", retrieve_ltm)
workflow.add_node("call_agent", call_agent)
workflow.add_node("call_ltm_agent", call_ltm_agent)
workflow.add_node("tools_node", tools_node)

# edges

workflow.set_entry_point("images")

workflow.add_edge("images", "pii_redaction")
workflow.add_edge("pii_redaction", "increase_current_messages_count")

workflow.add_edge("increase_current_messages_count", "retrieve_ltm")
workflow.add_edge("retrieve_ltm", "call_agent")
workflow.add_edge("retrieve_ltm", "call_ltm_agent")

workflow.add_edge("call_ltm_agent", END)

workflow.add_conditional_edges("call_agent", tools_router)
workflow.add_conditional_edges("tools_node", route_after_tools)


memory = CosmosDBSaverSync(
    database_name=COSMOS_DATABASE_NAME,
    container_name=COSMOS_CHECKPOINTS_CONTAINER_NAME,
    endpoint=COSMOS_ENDPOINT
)

store = CosmosDBStore.from_endpoint(
    endpoint=COSMOS_ENDPOINT,
    credential=credential,
    database_name=COSMOS_DATABASE_NAME,
    container_name=COSMOS_CONTAINER_NAME
)
store.setup()

app = workflow.compile(checkpointer=memory, store=store)


if __name__ == "__main__":

    def display_agent_response(response_state):
        messages = response_state.get("messages", [])
        if not messages:
            return

        # Find the start of the current turn (messages following the latest HumanMessage)
        last_human_idx = -1
        for i in range(len(messages) - 1, -1, -1):
            if isinstance(messages[i], HumanMessage):
                last_human_idx = i
                break

        current_turn_msgs = messages[last_human_idx + 1:] if last_human_idx != -1 else messages

        for msg in current_turn_msgs:
            if isinstance(msg, AIMessage):
                has_respond = hasattr(msg, "tool_calls") and any(tc.get("name") == "respond" for tc in (msg.tool_calls or []))

                # If the assistant spoke directly or added thoughts alongside non-respond tools
                if msg.content and not has_respond:
                    print("\nAgent:", msg.content)

                if hasattr(msg, "tool_calls") and msg.tool_calls:
                    for tc in msg.tool_calls:
                        tool_name = tc.get("name")
                        tool_args = tc.get("args", {})

                        if tool_name == "respond":
                            print("\nAgent:", tool_args.get("response", ""))
                            citations = tool_args.get("citations")
                            if citations:
                                print("\nCitations:")
                                for c in citations:
                                    c_dict = c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else str(c))
                                    b_id = c_dict.get('book_id') or c_dict.get('book_ids')
                                    p_num = c_dict.get('page_number') or c_dict.get('page_numbers')
                                    print(f"  - Book ID: {b_id}, Page: {p_num}, Grade: {c_dict.get('grade')}")

                        elif tool_name == "quiz":
                            print(f"\n[Tool Used: quiz]")
                            questions = tool_args.get("questions", []) if isinstance(tool_args, dict) else []
                            if not questions:
                                print(f"Parameters: {tool_args}")
                            else:
                                print(f"Parameters: {len(questions)} question(s)")
                                print("\n" + "=" * 50)
                                print(f"QUIZ ({len(questions)} Question{'s' if len(questions) != 1 else ''}):")
                                print("=" * 50)
                                for idx, q in enumerate(questions, start=1):
                                    if isinstance(q, str):
                                        print(f"\nQuestion {idx}: {q}")
                                        continue
                                    q_dict = q if isinstance(q, dict) else (q.model_dump() if hasattr(q, "model_dump") else vars(q))
                                    q_type = q_dict.get("type", "")
                                    q_text = q_dict.get("question_text", "")
                                    options = q_dict.get("options", [])
                                    type_str = f" [{q_type}]" if q_type else ""

                                    print(f"\nQuestion {idx}{type_str}: {q_text}")
                                    if options:
                                        for opt_idx, opt in enumerate(options):
                                            opt_str = str(opt).strip()
                                            if any(opt_str.startswith(p) for p in ["A)", "B)", "C)", "D)", "A.", "B.", "C.", "D."]):
                                                print(f"  {opt_str}")
                                            else:
                                                letter = chr(65 + opt_idx) if opt_idx < 26 else str(opt_idx + 1)
                                                print(f"  {letter}) {opt_str}")
                                print("=" * 50)

                        else:
                            print(f"\n[Tool Used: {tool_name}]")
                            if tool_args:
                                print(f"Parameters: {tool_args}")
                            else:
                                print("Parameters: None")


    print("Starting the app")

    student_grade = input("Enter your grade (e.g. 10): ").strip() or "10"
    print(f"Configured for Grade: {student_grade}\n")

    # init memory
    config = {
        "configurable": {
            "thread_id": input("Enter your thread ID: ") ,
            "user_id": "1",
            "name": "Ahmed",
            "age": "16",
            "gender": "Male",
            "grade": student_grade,
            "language": "Arabic",
            "country": "Egypt",
            "exam_prep": False,
            "images": [r"F:\Projects\AILP\tests\data\image.png"] # delete later for professional release
        }
    }

    user_query = ""
    while user_query.lower() != "quit":
        user_query = input("You: ")
        if user_query.lower() == "quit" or not user_query.strip():
            break
        latency_tracker.reset()
        try:
            with tracer.start_as_current_span("agent_turn") as turn_span:
                turn_span.set_attribute("gen_ai.conversation.id", config["configurable"]["thread_id"])
                turn_span.set_attribute("user_id", config["configurable"]["user_id"])
                response = app.invoke({"messages": [{"role": "user", "content": user_query}]}, config=config)

                display_agent_response(response)
                print("-="*100)
                print("preferences: ", response["preferences"])
                print("study_preferences: ", response["study_preferences"])
        finally:
            latency_tracker.print_summary()
