from types import SimpleNamespace
from services.agent.llm_text import ai_text

def test_ai_text_handles_str_and_message_objects():
    assert ai_text("  hello world  ") == "hello world"
    msg = SimpleNamespace(content="  Pod is healthy. \n")
    assert ai_text(msg) == "Pod is healthy."


def test_ai_text_normalizes_list_of_blocks():
    gemini_msg = SimpleNamespace(
        content=[
            "First paragraph.",
            {"type": "text", "text": "Second paragraph from block."},
            {"type": "tool_use", "id": "ignored"},
        ]
    )
    assert ai_text(gemini_msg) == "First paragraph.\nSecond paragraph from block."
