from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.prebuilt import create_react_agent
from langgraph.graph.graph import CompiledGraph
from dotenv import load_dotenv

load_dotenv()



def create_ollama_agent(MODEL: str, GOOGLE_API_KEY: str):
    llm = ChatGoogleGenerativeAI(
        model=MODEL,
        google_api_key=GOOGLE_API_KEY,
        temperature=0,
        convert_system_message_to_human=True
    )
    agent = create_react_agent(llm, tools=[])
    return agent

async def run_ollama(ollama_agent: CompiledGraph, prompt: str):
    agent_response = await ollama_agent.ainvoke(
        {"messages": prompt}
    )
    message = agent_response["messages"][-1].content
    return str(message)