import asyncio
import logging
from autogen_ext.models.openai import (AzureOpenAIChatCompletionClient)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from typing import Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import HandoffTermination
from autogen_agentchat.base import TerminationCondition, TerminatedException
from autogen_agentchat.messages import HandoffMessage, AgentEvent, ChatMessage, StopMessage, TextMessage
from autogen_agentchat.teams import Swarm
from autogen_agentchat.ui import Console
from autogen_core.memory import ListMemory, MemoryContent, MemoryMimeType
# from autogen_ext.memory.chromadb import ChromaDBVectorMemory, PersistentChromaDBVectorMemoryConfig
from auto_gen_explore import config
from auto_gen_explore.memory import ListMemory2
from auto_gen_explore.plugins.lights import LightsPlugin
from auto_gen_explore.plugins.meals import MealsPlugin
from auto_gen_explore.plugins.utils import Console2

# https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit
grey = '\x1b[38;5;8m'
yellow = '\x1b[38;5;226m'
dark_yellow = '\x1b[38;5;214m'
reset = '\x1b[0m'


logging.basicConfig(
    # format="[%(asctime)s - %(name)s:%(lineno)d - %(levelname)s] %(message)s",
    format=f"{grey}%(message)s{reset}",
    datefmt="%Y-%m-%d %H:%M:%S",
    # level=logging.DEBUG
)

# logging.getLogger("httpx").setLevel(logging.INFO) # useful to see the URLs used (e.g. when debugging a 404 for AOAI)
logging.getLogger("kernel").setLevel(config.semantic_kernel_log_level())
logging.getLogger("AIAgent").setLevel(config.agent_log_level())

# Create the token provider
api_key = config.openai_key_if_set()
if api_key:
    token_provider = None
else:
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/models.html#azure-openai
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment=config.openai_deployment_name(),
    model=config.openai_model_name(),
    api_version=config.openai_api_version(),
    azure_endpoint=config.openai_endpoint(),
    # Optional if you choose key-based authentication.
    azure_ad_token_provider=token_provider,
    api_key=api_key,
    # api_key="sk-...", # For key-based authentication.
)

lights_plugin = LightsPlugin()
meals_plugin = MealsPlugin()


triage_agent = AssistantAgent(
    "triage_agent",
    model_client=model_client,
    system_message="You are a bot to help users. "
    "Introduce yourself. Always be very brief. "
    "For food related questions, transfer to the meals agent. "
    "Gather information to direct the customer to the right agent."
    "But make your questions subtle and natural."
    "Don't output a message when transferring to another agent.",
    handoffs=["meals_agent", "lights_agent", "user"],
    reflect_on_tool_use=False,
)

lights_agent = AssistantAgent(
    "lights_agent",
    model_client=model_client,
    tools=[lights_plugin.get_state, lights_plugin.change_state],
    system_message="You are a an agent that can provide information on the status of lights and turn lights on and off."
    "Always answer in a sentence or less."
    "Transfer to the the triage agent if you can't help. Transfer to the user agent after performing the requested lights actions.",
    handoffs=["triage_agent", "user"],
)

  

# meals_agent_memory = ListMemory()
meals_agent_memory = ListMemory2()
# meals_agent_memory = ChromaDBVectorMemory()
# async def save_to_memory(content: str) -> None:
#     """Function to save the meals agent memory to a file"""
#     await meals_agent_memory.add(MemoryContent(content=content, mime_type=MemoryMimeType.TEXT))
async def save_to_memory(content: str, preference_type:str) -> None:
    """Function to save the meals agent preferences"""
    q = await meals_agent_memory.query(MemoryContent(content="", mime_type=MemoryMimeType.TEXT, metadata={"preference": preference_type}))
    if len(q.results) > 0:
        # Update existing preference
        # NOTE - this probably only works for in-memory Memory
        q.results[0].content = content
    else:
        await meals_agent_memory.add(MemoryContent(content=content, mime_type=MemoryMimeType.TEXT, metadata={"preference": preference_type}))

meals_agent = AssistantAgent(
    "meals_agent",
    model_client=model_client,
    tools=[meals_plugin.add_meal, meals_plugin.get_dish_options, meals_plugin.get_dishes, meals_plugin.get_meal_steps,
           meals_plugin.get_time_to_be_ready, meals_plugin.remove_dish, meals_plugin.set_time_to_be_ready, 
           save_to_memory],
    system_message="You are a an agent that can provide information about dishes for meals."
    "You can also use tools to add dishes to meals, remove dishes from meals and get the steps for preparing a meal."
    "Answer in a sentence or less except when showing meal steps. In that case show a list of steps in time order."
    # "Transfer to the user if you have questions about the meal.",
    "Transfer to the the triage agent if you can't help. Transfer to the user agent after performing the requested meals actions."
    "If the user doesn't specify if a meal is frozen, default to their preference if stored in memory. If no preference is stored, ask the user and save to memory (using preference_type of fresh_or_frozen).",
    handoffs=["triage_agent", "user"],
    memory= [meals_agent_memory]
)
# user_agent = UserProxyAgent("user")

class AgentTextMessageTermination(TerminationCondition):
    """Class that attempts to inject a handoff to the user agent when a text message is received from the agent"""


    def __init__(self) -> None:
        self._terminated = False

    @property
    def terminated(self) -> bool:
        return self._terminated

    async def __call__(self, messages: Sequence[AgentEvent | ChatMessage]) -> StopMessage | None:
        if self.terminated:
            raise TerminatedException("Termination condition has already been reached")
        if len(messages) == 0:
            return None
        # # print(f"{yellow}!!!messages {messages} {reset}")
        print(f"{yellow}!!!messages-start")
        for message in messages:
            print(f"  {message}")
        print(f"{yellow}!!!messages-end {reset}")
        
        # Stop on first text message not from user
        # May want to change this to stop on first message that isn't handoff or function call etc
        if isinstance(messages[-1], TextMessage) and messages[-1].source != "user":
            # self._terminated = True
            # raise TerminatedException("Got TextMessage")
            return StopMessage(content="TextMessage received", source=self.__class__.__name__)
            # return HandoffMessage(target="user", source=self.__class__.__name__, content="TextMessage received from agent - ask user for input")

    async def reset(self) -> None:
        self._terminated = False

termination=HandoffTermination(target="user")
# termination=HandoffTermination(target="user") | AgentTextMessageTermination()
team=Swarm(
    participants=[triage_agent, lights_agent, meals_agent],
    termination_condition=termination,
)

async def run_team_stream() -> None:
    user_message=input("User (type 'exit' to close the session): ")
    if user_message.strip().lower() == "exit":
        return
    task_result=await Console2(team.run_stream(task=user_message))
    last_message=task_result.messages[-1]

    while isinstance(last_message, HandoffMessage) and last_message.target == "user": # use this normally (i.e. not using AgentTextMessageTermination)
    # while True: # use this if using AgentTextMessageTermination
        print(meals_agent_memory.content)
        user_message=input("User (type 'exit' to close the session): ")
        if user_message.strip().lower() == "exit":
            return

        task_result=await Console2(
            team.run_stream(task=HandoffMessage(
                source="user", target=last_message.source, content=user_message))
        )
        last_message=task_result.messages[-1]


# Use asyncio.run(...) if you are running this in a script.




async def foo():
    await meals_agent_memory.add(MemoryContent(content="metric", mime_type=MemoryMimeType.TEXT, metadata={"preference": "units"}))
    await meals_agent_memory.add(MemoryContent(content="fresh", mime_type=MemoryMimeType.TEXT, metadata={"preference": "frozen_or_fresh"}))
    print(meals_agent_memory.content)
    print("========================")

    # q = await meals_agent_memory.query("preference")
    # q = await meals_agent_memory.query("frozen_or_fresh")
    q = await meals_agent_memory.query(MemoryContent(content="", mime_type=MemoryMimeType.TEXT, metadata={"preference": "frozen_or_fresh"}))
    print(q)
    q.results[0].content = "test2"
    
    print("========================")
    print(meals_agent_memory.content)
    

# asyncio.run(foo())

asyncio.run(run_team_stream())


