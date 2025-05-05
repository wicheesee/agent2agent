from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph.graph import CompiledGraph
from dotenv import load_dotenv

from langchain.tools import StructuredTool
from datetime import datetime
import pytz
from pydantic import BaseModel, Field

class GetCurrentTimeArgs(BaseModel):
    timezone: str = Field(default="Asia/Jakarta", description="Zona waktu untuk mendapatkan waktu saat ini")
# Define tools

def get_current_time(timezone: str = "Asia/Jakarta") -> str:
    """Mendapatkan waktu saat ini berdasarkan timezone"""
    tz = pytz.timezone(timezone)
    current_time = datetime.now(tz)
    return current_time.strftime("%Y-%m-%d %H:%M:%S %Z")

# Register tools
time_tools = [
    StructuredTool.from_function(
        func=get_current_time,
        name="get_current_time",
        description="Mendapatkan waktu saat ini berdasarkan timezone",
        args_schema=GetCurrentTimeArgs
    )
]

load_dotenv()

def create_ollama_agent(MODEL: str, GOOGLE_API_KEY: str):
    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
        convert_system_message_to_human=True
    )
    agent = create_react_agent(llm, tools=time_tools)
    return agent

async def run_ollama(ollama_agent: CompiledGraph, prompt: str):
    agent_response = await ollama_agent.ainvoke(
        {"messages": prompt}
    )
    message = agent_response["messages"][-1].content
    return str(message)