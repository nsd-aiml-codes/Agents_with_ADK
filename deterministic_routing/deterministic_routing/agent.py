from google.adk.agents import LlmAgent, BaseAgent
from google.adk.tools.agent_tool import AgentTool
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.adk.events.event import Event
from google.adk.events.event_actions import EventActions
from google.adk.models.lite_llm import LiteLlm
from google.adk.tools import FunctionTool
from google.adk.tools.tool_context import ToolContext

from google.adk.tools import AgentTool
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents import BaseAgent, Agent
from google.adk.runners import Runner
from google.genai import types
from dotenv import load_dotenv
import logging
import warnings
import asyncio
warnings.filterwarnings(
    "ignore",
    message="Pydantic serializer warnings:.*"
)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s'
)
import os
load_dotenv()
import uuid
import datetime
import logging


# ================================================================================LiteLLM=======================================================================
os.environ["OLLAMA_API_BASE"] = ""
os.environ["LITELLM_DISABLE_COST"] = "True"
os.environ["LITELLM_LOG_GET_MODEL_INFO"] = "False"
os.environ["LITELLM_LOGGING_DISABLE"] = "True"

custom_model = LiteLlm(
    model="ollama/deepseek-r1:14b", 
    api_base="",
    stream = False

)

# ==============================================================================================================================================================

class DeterministicRouter(BaseAgent):
    _agent_a = None
    _agent_b = None
    model_config = {"arbitrary_types_allowed": True, "extra": "ignore"}

    def __init__(self, agent_a: BaseAgent, agent_b: BaseAgent, name, description):
        # Initialize the base class with required metadata
        super().__init__(name=name,
            description=description, sub_agents = [agent_a, agent_b])
        
        self._agent_a = agent_a
        self._agent_b = agent_b


    async def _run_async_impl(self, ctx: InvocationContext):
        """
        Routes the request based on the user's input found in the context.
        """
        
        logging.info(f"invocation context - {ctx.user_content}")
        parts = ctx.user_content.parts if ctx.user_content else []
        logging.info(f"invocation context parts - {parts}")
        user_text = "".join(getattr(p, 'text', '') or "" for p in parts).strip()
        logging.info(f"invocation context user_text - {user_text}")

        if "research" in user_text:
            target_agent = self.sub_agents[0]
        else:
            target_agent = self.sub_agents[1]
        
        final_response = None
        async for event in target_agent.run_async(ctx):
            yield event

        

research_agent = Agent(
    name="research_agent", 
    model=custom_model, 
    description="SPECIALIST: Handles academic papers, scientific data, and deep research queries.",
    output_key = 'final_research'
)

general_agent = Agent(
    name="general_agent", 
    model=custom_model, 
    description="GENERALIST: Handles casual conversation, basic facts, and general daily questions.",
    instruction = "You are helpful assitant. Always produce final textual answer.",
    output_key = 'final_answer'
)

rg = DeterministicRouter(
    agent_a=research_agent, 
    agent_b=general_agent, 
    name="RootRouter",
    description="ROUTING TOOL: Must be used for ALL user inputs to determine if they are research-based or general in nature."
)


root_agent = LlmAgent(
    name = 'Root_agent',
    model = custom_model,
    description = 'You are helpful assistance.',
    instruction = "You are helpful assistant that will rout user query to RootRouter.",
    tools = [AgentTool(rg)]
)

session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()


async def main(app_name, userid, sessionid):
    runner = Runner(
        agent = root_agent,
        app_name = app_name,
        session_service = session_service,
        artifact_service = artifact_service
    )

    await runner.session_service.create_session(
        app_name = app_name,
        user_id = userid,
        session_id = sessionid,
        state = {}
    )

    while True:
        user_input = input("You:")
        resp = await async_main(user_input, sessionid, userid, runner)
        print("AGENT: {resp}")


async def process_event(event):
    response = None
    if event.is_final_response():
        if (event.content and event.content.parts and hasattr(event.content.parts[0], 'text') and event.content.parts[0].text):
            response =  event.content.parts[0].text.strip()
    return response


async def async_main(query, sessionid, userid, runner):
    content = types.Content(role ='user', parts = [types.Part(text = query)])

    main_response = None
    async for event in runner.run_async(user_id = userid, session_id = sessionid, new_message = content):
        final_response = await process_event(event)
        if final_response:
            main_response = final_response
    
    return main_response


if __name__ == '__main__':

    app_name = 'DeterministicRouting'
    userid = 'Firstuser'
    sessionid = str(uuid.uuid4())

    asyncio.run(main(app_name, userid, sessionid))
