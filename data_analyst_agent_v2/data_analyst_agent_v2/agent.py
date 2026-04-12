

from google.adk.agents import LlmAgent, Agent, BaseAgent
import os
from google.adk.tools import FunctionTool
from pydantic import BaseModel, Field, field_validator
from typing import List, Dict, Literal
from decimal import Decimal
from google.adk.tools.agent_tool import AgentTool
from google.adk.agents import LlmAgent, Agent, LoopAgent, SequentialAgent
from decimal import Decimal
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.base_tool import BaseTool
from google.adk.agents.callback_context import CallbackContext
from typing import Optional, Any
from google.genai.types import Content, Part
import google.genai.types as types
import warnings
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from toon import encode, decode
from google.adk.planners import BuiltInPlanner
import asyncio
import gzip
import plotly.io as pio
from google.adk.runners import Runner
from mcp.types import CallToolResult
import base64
from data_analyst_agent_v2.prompts import VISUALIZATION_PROMPT, SQL_SPECIALIST_PROMPT, ROUTING_PROMPT
from data_analyst_agent_v2.tools import load_master_data_tool, set_state, after_tool_artifact_save, MainRouter, VIZ_INPUT, toolset
warnings.filterwarnings("ignore", category=UserWarning, module=".*google\\.adk.*")
import json


session_service = InMemorySessionService()
artifact_service = InMemoryArtifactService()


visualization_tool = LlmAgent(
   name = 'VISUALIZE_agent',
   model = "gemini-2.5-flash",
   description = 'You are specialized Visualizer + Validator for sql query using plotly.',
   instruction = VISUALIZATION_PROMPT,
   input_schema = VIZ_INPUT,
   tools = [toolset, load_master_data_tool, set_state],
   after_tool_callback = after_tool_artifact_save)


sql_specialist = LlmAgent(
   name = 'SQL_APECIALIST',
   model = "gemini-2.5-flash",
   description = 'You are specialized text-to-sql Agent to Generate SQL query from user question.',
   instruction = SQL_SPECIALIST_PROMPT,
   tools = [toolset, load_master_data_tool, set_state],
   after_tool_callback = after_tool_artifact_save
)

root_agent = LlmAgent(
   name = 'Text_to_sql_router',
   model = "gemini-2.5-flash",
   description = 'You are specialized text-to-sql Agent Router.',
   instruction = ROUTING_PROMPT,
   tools = [toolset, load_master_data_tool, AgentTool(sql_specialist), set_state, AgentTool(visualization_tool)],
   after_tool_callback = after_tool_artifact_save
)


runner = Runner(
    agent = root_agent,
    app_name = "Data-aNaLySt",
    session_service = session_service,
    artifact_service = artifact_service
)
