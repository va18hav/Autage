from typing import Any


def ai_text(result: Any) -> str:
    """
    Extract plain text from an LLM ainvoke() result.

    AIMessage.content is usually a str, but Gemini (and other providers) can
    return a list of content blocks. Normalize both shapes into one string —
    nodes previously called .content.strip() directly, which crashed with
    "'list' object has no attribute 'strip'" on list-shaped responses.
    """
    content = getattr(result, "content", result)

    if isinstance(content, str):
        return content.strip()

    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and isinstance(block.get("text"), str):
                parts.append(block["text"])
        return "\n".join(parts).strip()

    return str(content).strip()
