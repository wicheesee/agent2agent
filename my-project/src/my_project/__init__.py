import logging
import asyncio
import click
from dotenv import load_dotenv
import google_a2a
from google_a2a.common.types import AgentSkill, AgentCapabilities, AgentCard
from google_a2a.common.server import A2AServer
from my_project.task_manager import MyAgentTaskManager
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
MODEL = "gemini-2.0-flash"

@click.command()
@click.option("--host", default="localhost")
@click.option("--port", default=10002)
# @click.option("--gemini-api", default=GOOGLE_API_KEY)
# @click.option("--gemini-model", default=None)
def main(host, port):
  skill = AgentSkill(
    id="my-project-echo-skill",
    name="Echo Tool",
    description="Echos the input given",
    tags=["echo", "repeater"],
    examples=["I will see this echoed back to me"],
    inputModes=["text"],
    outputModes=["text"],
  )
  logging.info(skill)
  time_skill = AgentSkill(
    id="my-project-time-skill",
    name="Current Time Tool",
    description="Gets the current time for a specified timezone (defaults to Asia/Jakarta).",
    tags=["time", "clock", "timezone"],
    examples=["What time is it in London?", "Current time please", "Jam berapa sekarang?"],
    inputModes=["text"],
    outputModes=["text"],
  )
  capabilities = AgentCapabilities(
    streaming=True
  )
  agent_card = AgentCard(
    name="Echo and Time Agents",
    description="This agent echos input OR can tell the current time.",
    url=f"http://{host}:{port}/",
    version="0.1.0",
    defaultInputModes=["text"],
    defaultOutputModes=["text"],
    capabilities=capabilities,
    skills=[skill, time_skill],
  )
  logging.info(agent_card)
  task_manager = MyAgentTaskManager(
    gemini_api=GOOGLE_API_KEY,
    gemini_model=MODEL,
  )
  server = A2AServer(
    agent_card=agent_card,
    task_manager=task_manager,
    host=host,
    port=port,
  )
  server.start()

if __name__ == "__main__":
  main()
