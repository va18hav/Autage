"""Per-run LLM resolution: which provider/model each pipeline step uses.

The worker loads one LlmResolver per incident run (two tiny queries), then the
resolver is installed for the duration of the run and every agent node calls
`get_llm(step_key)` — no node knows about concrete provider SDKs.
"""





class LlmConfigError(RuntimeError):
    """A user-fixable configuration problem (missing provider credential,
    unknown provider/model). Message is safe to surface in incident errors."""
