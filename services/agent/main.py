import os
os.environ["MOCK_KUBECTL"] = "true"   # use mock kubectl responses — no real cluster needed

from dotenv import load_dotenv
load_dotenv()

from services.agent.graph import builder
from services.agent.mock.alerts import MOCK_INCIDENT
import json

graph = builder.compile()

if __name__ == "__main__":
    print("--- Running SRE Agent Graph ---")
    result = graph.invoke(MOCK_INCIDENT)
    print("\n--- Final Graph State ---")
    print(json.dumps(result, indent=2, default=str))