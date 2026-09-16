"""
Realistic mock responses for every kubectl tool.
These simulate what you'd actually get back from a cluster
running the auth-service OOMKill scenario (INC-1042).

The get_mock_response() function is called by tools/kubectl.py
when the MOCK_KUBECTL=true env var is set.
"""


# ── Individual mock outputs ───────────────────────────────────────────────────

_POD_LOGS = """\
2026-09-30T12:40:01Z INFO  auth-service starting up version=2.4.1
2026-09-30T12:40:02Z INFO  Connected to database pool_size=20
2026-09-30T12:40:15Z INFO  Token validation cache warmed entries=50000
2026-09-30T12:41:03Z INFO  Serving requests port=8080
2026-09-30T12:42:11Z WARN  Heap usage elevated heap_used=820MB heap_limit=950MB
2026-09-30T12:42:45Z WARN  GC pause exceeded threshold pause_ms=1800 threshold_ms=500
2026-09-30T12:43:02Z WARN  Heap usage critical heap_used=910MB heap_limit=950MB
2026-09-30T12:43:10Z ERROR Cache eviction failing — no free memory available
2026-09-30T12:43:18Z ERROR Failed to process token refresh request: out of memory
2026-09-30T12:43:21Z FATAL signal: killed
"""

_POD_LOGS_PREVIOUS = """\
2026-09-30T12:35:00Z INFO  auth-service starting up version=2.4.1
2026-09-30T12:35:01Z INFO  Connected to database pool_size=20
2026-09-30T12:36:44Z WARN  Heap usage elevated heap_used=800MB heap_limit=950MB
2026-09-30T12:37:30Z WARN  Large in-memory session cache detected entries=120000 expected_max=50000
2026-09-30T12:38:12Z WARN  GC pause exceeded threshold pause_ms=2300 threshold_ms=500
2026-09-30T12:38:55Z ERROR Heap dump requested but insufficient memory to write
2026-09-30T12:39:01Z FATAL Out of memory: Kill process 1 (auth-service) score 999 or sacrifice child
Killed
"""
