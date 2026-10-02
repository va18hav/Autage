import os
import asyncio
os.environ["MOCK_KUBECTL"] = "true"   # use mock kubectl responses — no real cluster needed

from dotenv import load_dotenv
load_dotenv()

from services.agent.graph import builder
from services.agent.mock.alerts import MOCK_INCIDENT
import json

graph = builder.compile()

async def main():
    
    print("--- Running SRE Agent Graph ---")
    result = await graph.ainvoke(MOCK_INCIDENT)
    print("\n--- Final Graph State ---")
    print(json.dumps(result, indent=2, default=str))

if __name__ == "__main__":
    asyncio.run(main())
