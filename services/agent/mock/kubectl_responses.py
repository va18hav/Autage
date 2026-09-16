"""
Realistic mock responses for every kubectl tool.
These simulate what you'd actually get back from a cluster
running the auth-service OOMKill scenario (INC-1042).

The get_mock_response() function is called by tools/kubectl.py
when the MOCK_KUBECTL=true env var is set.
"""
