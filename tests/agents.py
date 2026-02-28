import os
from pathlib import Path
from dotenv import load_dotenv
from strands import Agent
from strands.models.mistral import MistralModel

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

model = MistralModel(
    api_key=os.getenv("MISTRAL_API"),
    model_id="ministral-3b-2512",
)

agent = Agent(model=model)

agent("Tell me about agentic AI")
