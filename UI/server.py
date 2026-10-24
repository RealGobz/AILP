"""
AILP Agent Web Server (aiohttp)
Provides REST API endpoints and serves the modern Phase 1 / Phase 2 UI.
"""
import os
import sys
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
import json
import asyncio
import base64
from pathlib import Path
from aiohttp import web

# Ensure root directory is on PYTHONPATH
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from Agent.agent import app
from Agent.Tools.utils.latency_tracker import latency_tracker

UI_DIR = Path(__file__).resolve().parent

DEFAULT_CONFIG = {
    "thread_id": "31",
    "user_id": "1",
    "name": "Ahmed",
    "age": "16",
    "gender": "Male",
    "grade": "10",
    "language": "Arabic",
    "country": "Egypt",
    "exam_prep": False,
    "images": [r"F:\Projects\AILP\tests\data\image.png"]
}


def parse_turn_response(result_state):
    """Extracts agent message, tool calls with arguments & outputs, citations, and quizzes."""
    messages = result_state.get("messages", [])
    last_human_idx = -1
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], HumanMessage):
            last_human_idx = i
            break

    current_turn_msgs = messages[last_human_idx + 1:] if last_human_idx != -1 else messages

    tool_results = {}
    for msg in current_turn_msgs:
        if isinstance(msg, ToolMessage):
            tool_results[msg.tool_call_id] = msg.content

    tools_used = []
    response_text = ""
    citations = []
    quiz_data = None

    for msg in current_turn_msgs:
        if isinstance(msg, AIMessage):
            has_respond = hasattr(msg, "tool_calls") and any(tc.get("name") == "respond" for tc in (msg.tool_calls or []))
            if msg.content and not has_respond:
                response_text = str(msg.content)

            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    t_name = tc.get("name")
                    t_args = tc.get("args", {})
                    t_id = tc.get("id")
                    t_out = tool_results.get(t_id, "")

                    tools_used.append({
                        "id": t_id,
                        "name": t_name,
                        "args": t_args,
                        "output": str(t_out)
                    })

                    if t_name == "respond":
                        response_text = t_args.get("response", "") or response_text
                        raw_cits = t_args.get("citations", [])
                        citations = [
                            c if isinstance(c, dict) else (c.model_dump() if hasattr(c, "model_dump") else vars(c))
                            for c in raw_cits
                        ]
                    elif t_name == "quiz":
                        raw_qs = t_args.get("questions", [])
                        quiz_data = [
                            q if isinstance(q, dict) else (q.model_dump() if hasattr(q, "model_dump") else vars(q))
                            for q in raw_qs
                        ]

    return {
        "response": response_text,
        "tools_used": tools_used,
        "citations": citations,
        "quiz": quiz_data,
        "preferences": result_state.get("preferences", []),
        "study_preferences": result_state.get("study_preferences", [])
    }


async def handle_index(request):
    return web.FileResponse(UI_DIR / "index.html")


async def handle_get_config(request):
    return web.json_response(DEFAULT_CONFIG)


async def handle_upload_image(request):
    """Handles image file upload or data URL and saves to tests/data/."""
    try:
        reader = await request.multipart()
        field = await reader.next()
        if not field:
            return web.json_response({"error": "No file field in upload"}, status=400)

        filename = field.filename or f"upload_{os.urandom(4).hex()}.png"
        save_dir = ROOT_DIR / "tests" / "data" / "uploads"
        save_dir.mkdir(parents=True, exist_ok=True)
        save_path = save_dir / filename

        size = 0
        with open(save_path, "wb") as f:
            while True:
                chunk = await field.read_chunk()
                if not chunk:
                    break
                size += len(chunk)
                f.write(chunk)

        return web.json_response({
            "status": "success",
            "path": str(save_path),
            "filename": filename,
            "size": size
        })
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def handle_chat(request):
    """Executes a turn in the LangGraph agent workflow."""
    try:
        data = await request.json()
        user_message = data.get("message", "").strip()
        config_override = data.get("config", {})
        images_override = data.get("images", None)

        if not user_message and not images_override:
            return web.json_response({"error": "Message or image is required"}, status=400)

        # Merge configurable
        configurable = dict(DEFAULT_CONFIG)
        configurable.update(config_override)

        if images_override is not None:
            configurable["images"] = images_override

        # Ensure correct types
        configurable["exam_prep"] = bool(configurable.get("exam_prep", False))
        configurable["thread_id"] = str(configurable.get("thread_id", "31")).strip() or "31"

        run_config = {"configurable": configurable}

        latency_tracker.reset()

        def _run_graph():
            input_state = {"messages": [{"role": "user", "content": user_message}]}
            return app.invoke(input_state, config=run_config)

        loop = asyncio.get_event_loop()
        result_state = await loop.run_in_executor(None, _run_graph)

        parsed = parse_turn_response(result_state)
        latencies = latency_tracker.records
        total_latency_ms = sum(r.get("duration_ms", 0.0) for r in latencies)

        return web.json_response({
            "status": "success",
            "response": parsed["response"],
            "tools_used": parsed["tools_used"],
            "citations": parsed["citations"],
            "quiz": parsed["quiz"],
            "preferences": parsed["preferences"],
            "study_preferences": parsed["study_preferences"],
            "latencies": latencies,
            "total_latency_ms": round(total_latency_ms, 2)
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return web.json_response({"error": str(e)}, status=500)


def create_app():
    app_instance = web.Application()
    app_instance.router.add_get("/", handle_index)
    app_instance.router.add_get("/api/config", handle_get_config)
    app_instance.router.add_post("/api/chat", handle_chat)
    app_instance.router.add_post("/api/upload", handle_upload_image)
    app_instance.router.add_static("/", UI_DIR)
    return app_instance


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting AILP UI server on http://localhost:{port}")
    web.run_app(create_app(), host="127.0.0.1", port=port)
