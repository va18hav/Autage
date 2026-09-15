from services.agent.llm.resolver import friendly_error

def test_friendly_error_formats_auth_and_generic_exceptions():
    auth_msg = friendly_error(RuntimeError("HTTP 401 Unauthorized: invalid api_key"))
    assert "Authentication with the LLM provider failed" in auth_msg

    other_msg = friendly_error(ValueError("timeout connecting"))
    assert other_msg == "ValueError: timeout connecting"
