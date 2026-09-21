import os

os.environ["MOCK_KUBECTL"] = "true"   # use mock kubectl responses — no real cluster needed

from dotenv import load_dotenv
load_dotenv()

from services.agent.graph import builder

graph = builder.compile()
