import os

from services.config import settings

# Keep the mock tooling switch working without real cluster access.
if settings.MOCK_KUBECTL:
    os.environ["MOCK_KUBECTL"] = "true"

from services.agent.graph import builder

# Compile the graph
agent_graph = builder.compile()
