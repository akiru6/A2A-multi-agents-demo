import os
import time
import json
import asyncio
import threading
import warnings
import logging
import traceback
import uuid

# --- Core A2A and ADK Imports ---
from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, MessageSendParams, SendMessageRequest
from a2a.client import A2AClient
from a2a.utils.constants import AGENT_CARD_WELL_KNOWN_PATH

from google.adk.agents import Agent
from google.adk.a2a.executor.a2a_agent_executor import (
    A2aAgentExecutor,
    A2aAgentExecutorConfig,
)
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.artifacts import InMemoryArtifactService
from google.adk.memory.in_memory_memory_service import InMemoryMemoryService
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import google.generativeai as genai
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset, StdioServerParameters, StdioConnectionParams
from google.adk.tools.function_tool import FunctionTool

# --- Imports for Our Specific Use Case ---
from dotenv import load_dotenv
import uvicorn
import httpx
import nest_asyncio
from tavily import TavilyClient

# --- Setup Logging and Warnings ---
logging.basicConfig(level=logging.INFO)
logging.getLogger("google_adk.google.adk.tools.base_authenticated_tool").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*EXPERIMENTAL.*")
warnings.filterwarnings("ignore", message=".*there are non-text parts in the response.*")


# ==============================================================================
# SECTION 1: SETUP & CONFIGURATION
# ==============================================================================
print("--- Section 1: Initializing Configuration ---")
nest_asyncio.apply()
load_dotenv()

# --- API Keys and Configuration ---
MODEL_NAME = "gemini-2.5-flash" # Using a more advanced model for better analysis
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GITHUB_PERSONAL_ACCESS_TOKEN = os.getenv("GITHUB_TOKEN")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
DLAI_LOCAL_URL = os.getenv("DLAI_LOCAL_URL", "http://127.0.0.1:{port}/")
OUTPUT_DIR = "output" # Directory to save local files

# --- A2A Agent Server Ports ---
ORCHESTRATOR_PORT = 10030
SCOUT_PORT = 10031
ANALYST_PORT = 10032

# --- GitHub MCP Server Connection (Only for Scout) ---
github_server_params = StdioServerParameters(
    command="docker",
    args=[
        "run", "--rm", "-i",
        "-e", f"GITHUB_PERSONAL_ACCESS_TOKEN={GITHUB_PERSONAL_ACCESS_TOKEN}",
        "ghcr.io/github/github-mcp-server:main"
    ],
    timeout=120
)
github_connection_params = StdioConnectionParams(server_params=github_server_params)

# Create output directory if it doesn't exist
os.makedirs(OUTPUT_DIR, exist_ok=True)


# SECTION 2: CUSTOM LOCAL TOOLS (New)
print("--- Section 2: Defining Custom Local & Web Search Tools ---")

# --- Define the raw Python functions ---
def save_file_locally(filename: str, content: str) -> str:
    """Saves text content to a local file in the 'output' directory."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully saved file to {filepath}"
    except Exception as e:
        return f"Error saving file: {e}"

def read_local_file(filename: str) -> str:
    """Reads text content from a local file in the 'output' directory."""
    filepath = os.path.join(OUTPUT_DIR, filename)
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found at {filepath}"
    except Exception as e:
        return f"Error reading file: {e}"

def tavily_search(query: str) -> str:
    """
    Performs a web search using the Tavily API to get up-to-date information
    on a given topic, focusing on business and marketing insights.
    """
    if not TAVILY_API_KEY:
        return "Tavily API key is not configured."
    try:
        client = TavilyClient(api_key=TAVILY_API_KEY)
        response = client.search(query=query, search_depth="advanced")
        return json.dumps(response['results'])
    except Exception as e:
        return f"Error during Tavily search: {e}"

# --- Manually create FunctionTool instances from the functions ---
save_file_locally_tool = FunctionTool(save_file_locally)
read_local_file_tool = FunctionTool(read_local_file)
tavily_search_tool = FunctionTool(tavily_search)

# ==============================================================================
# SECTION 3: AGENT DEFINITIONS 智能体定义
# ==============================================================================
print("--- Section 3: Defining Our Specialist Agents ---")

# --- Agent 1: GitHub 探索智能体
github_scout_agent = Agent(
    model=MODEL_NAME,
    name="github_scout_agent",
    instruction="""You are a data scout. Your mission is to find GitHub repositories and save the findings locally in a readable format.
1.  **Search:** Use the `search_repositories` tool to find the top 5 repositories matching the user's query.
2.  **Format:** Convert the list of repositories into a human-readable Markdown list. For each repository, include its name, URL, and description.
3.  **Save Locally:** Use the `save_file_locally` tool to save this Markdown list to the file named 'repository_list.md'.
4.  **Confirm:** Respond to the user with a confirmation message: "Intelligence gathered. Top 5 repository details have been saved to output/repository_list.md." """,
    tools=[
        McpToolset(
            connection_params=github_connection_params,
            tool_filter=["search_repositories"], # Only needs search now
        ),
        save_file_locally_tool # Added local save tool
    ],
)
github_scout_card = AgentCard(
    name="GitHub Scout",
    url=DLAI_LOCAL_URL.format(port=SCOUT_PORT),
    description="Finds GitHub repositories and saves a readable list locally.",
    version="2.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[AgentSkill(id="search_repos_local", name="Search and Save Repos", description="Searches for repositories and saves them to a local file.", tags=["github", "search", "local_save"])]
)


# --- Agent 2: 商业分析师
github_analyst_agent = Agent(
    model=MODEL_NAME,
    name="github_analyst_agent",
    instruction="""You are a strategic business analyst. Your goal is to create a marketing plan for open-source projects.
1.  **Read Briefing:** Use the `read_local_file` tool to read the 'repository_list.md' file. This contains the list of projects to analyze.
2.  **Conduct Research:** For each project in the list, use the `tavily_search` tool to research its commercial potential. Use queries like "[project name] business use cases", "[project name] target audience", or "[project name] competitors".
3.  **Synthesize & Plan:** Based on your research, create a comprehensive marketing plan in Markdown format. The plan should cover all projects from the list and include these sections for each:
    *   **Project Overview:** Briefly describe the project.
    *   **Target Audience:** Who are the ideal users or customers? (e.g., "Data Scientists at startups", "Enterprise DevOps teams").
    *   **Potential Business Models:** How could this project make money? (e.g., "SaaS offering", "Consulting services", "Paid enterprise features").
    *   **Key Messaging:** What is the core value proposition? (e.g., "The fastest way to build AI agents", "Secure and scalable infrastructure").
    *   **Suggested Marketing Channels:** Where to reach the target audience? (e.g., "Content marketing on dev.to", "Sponsoring AI newsletters", "Presenting at KubeCon").
4.  **Save Final Work:** Use the `save_file_locally` tool to save the complete marketing plan to 'marketing_plan.md'.
5.  **Confirm:** Respond to the user: "Business analysis complete. The marketing plan has been saved to output/marketing_plan.md." """,
    tools=[
        read_local_file_tool,   
        save_file_locally_tool, 
        tavily_search_tool      # 使用实例
    ],
)
github_analyst_card = AgentCard(
    name="GitHub Analyst",
    url=DLAI_LOCAL_URL.format(port=ANALYST_PORT),
    description="Analyzes a local list of repositories to create a detailed marketing plan.",
    version="2.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain"],
    skills=[AgentSkill(id="create_marketing_plan", name="Create Marketing Plan", description="Generates a marketing plan from a local repo list.", tags=["business", "analysis", "marketing"])]
)


# --- Agent 3: 项目总监
remote_github_scout = RemoteA2aAgent(
    name="github_repository_scout",
    description="Use this agent for tasks involving **searching or finding** repositories. It will find repositories and save the list to a local file for the analyst to use later.",
    agent_card=DLAI_LOCAL_URL.format(port=SCOUT_PORT).strip('/') + AGENT_CARD_WELL_KNOWN_PATH,
)
remote_github_analyst = RemoteA2aAgent(
    name="github_repository_analyst",
    description="Use this agent for tasks involving **analyzing, creating reports, or generating a marketing plan** from a pre-existing local list of repositories.",
    agent_card=DLAI_LOCAL_URL.format(port=ANALYST_PORT).strip('/') + AGENT_CARD_WELL_KNOWN_PATH,
)

orchestrator_agent = Agent(
    model=MODEL_NAME,
    name="team_lead_agent",
    instruction="""You are an expert AI Orchestrator. Your job is to delegate a user's request to the single most appropriate specialist agent. You do not perform tasks yourself.

**Your Specialist Agents:**
1.  `github_repository_scout`: Use for **searching and discovering** repositories. This agent finds repos and saves a list locally.
2.  `github_repository_analyst`: Use for **analyzing or creating a marketing plan**. This agent reads the local list and generates a report.

**Your Decision Process:**
-   If the prompt is about **finding** or **searching** for repos (e.g., "Find the top repos for 'AI agents'"), delegate to `github_repository_scout`.
-   If the prompt is about **analyzing** a list or **creating a report/plan** (e.g., "Analyze the saved list", "Create the marketing plan"), delegate to `github_repository_analyst`.

You only call one agent per user request. Do not chain agents.
""",
    sub_agents=[remote_github_scout, remote_github_analyst],
)
orchestrator_card = AgentCard(
    name="Orchestrator Agent",
    url=DLAI_LOCAL_URL.format(port=ORCHESTRATOR_PORT),
    description="The main coordinator that helps you find and analyze GitHub projects.",
    version="2.0",
    capabilities=AgentCapabilities(streaming=True),
    default_input_modes=["text/plain"],
    default_output_modes=["text/plain", "application/json"],
    skills=[AgentSkill(id="find_and_analyze", name="Find and Analyze Repos", description="Coordinates a search and analysis workflow.", tags=["orchestration", "workflow", "github"])]
)


# ==============================================================================
# SECTION 4: A2A SERVER INFRASTRUCTURE (Unchanged)
# ==============================================================================
servers = []
def create_agent_a2a_server(agent: Agent, agent_card: AgentCard) -> A2AStarletteApplication:
    # ... (This section remains identical to your original code)
    runner = Runner(
        app_name=agent.name,
        agent=agent,
        artifact_service=InMemoryArtifactService(),
        session_service=InMemorySessionService(),
        memory_service=InMemoryMemoryService(),
    )
    config = A2aAgentExecutorConfig()
    executor = A2aAgentExecutor(runner=runner,config=config)
    request_handler = DefaultRequestHandler(
        agent_executor=executor,
        task_store=InMemoryTaskStore(),
    )
    return A2AStarletteApplication(agent_card=agent_card, http_handler=request_handler)

def run_agent_in_background(create_agent_function, port, name):
    # ... (This section remains identical to your original code)
    def run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            print(f"🚀 Starting '{name}' agent on port {port}...")
            app = create_agent_function()
            config = uvicorn.Config(app.build(), host="0.0.0.0", port=port, log_level="info", loop="asyncio")
            server = uvicorn.Server(config)
            servers.append(server)
            loop.run_until_complete(server.serve())
        except Exception as e:
            print(f"❌ FATAL Error running '{name}' agent thread: {e}")
            traceback.print_exc()
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread

# ==============================================================================
# SECTION 5: MAIN EXECUTION BLOCK (Updated with new API key check)
# ==============================================================================
def main():
    """Synchronous main function to launch and monitor agent servers."""
    print("\n--- Section 4: Starting A2A Agent Servers ---")
    scout_thread = run_agent_in_background(
        lambda: create_agent_a2a_server(github_scout_agent, github_scout_card),
        SCOUT_PORT, "GitHub Scout"
    )
    analyst_thread = run_agent_in_background(
        lambda: create_agent_a2a_server(github_analyst_agent, github_analyst_card),
        ANALYST_PORT, "GitHub Analyst"
    )
    orchestrator_thread = run_agent_in_background(
        lambda: create_agent_a2a_server(orchestrator_agent, orchestrator_card),
        ORCHESTRATOR_PORT, "Orchestrator"
    )

    print("\n--- Waiting for servers to initialize (10 seconds)... ---")
    time.sleep(10)

    all_running = (scout_thread.is_alive() and analyst_thread.is_alive() and orchestrator_thread.is_alive())
    if all_running:
        print("✅ All agent servers appear to be running.")
        print(f"Orchestrator is available at port {ORCHESTRATOR_PORT}.")
        print("You can now run a client in a separate terminal to interact with it.")
        print("Press CTRL+C to shut down all servers.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n👋 Shutting down servers...")
    else:
        print("❌ One or more agent servers failed to start.")


if __name__ == "__main__":
    if not all([GEMINI_API_KEY, GITHUB_PERSONAL_ACCESS_TOKEN, TAVILY_API_KEY]):
        print("❌ Error: GEMINI_API_KEY, GITHUB_TOKEN, and TAVILY_API_KEY must be set in your .env file.")
    else:
        genai.configure(api_key=GEMINI_API_KEY)
        main()