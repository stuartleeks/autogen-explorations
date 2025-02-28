import asyncio
import logging
from typing import Sequence

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from autogen_core.model_context import BufferedChatCompletionContext
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination
from autogen_agentchat.messages import AgentEvent, ChatMessage
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console

from auto_gen_explore.plugins.lights import LightsPlugin
from auto_gen_explore.plugins.meals import MealsPlugin

# Set the logging level for  semantic_kernel.kernel to DEBUG.
logging.basicConfig(
    format="[%(asctime)s - %(name)s:%(lineno)d - %(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    # level=logging.DEBUG
)
logging.getLogger("kernel").setLevel(config.semantic_kernel_log_level())
logging.getLogger(
    "auto_gen_explore.plugins.lights").setLevel(config.lights_plugin_log_level())
logging.getLogger(
    "auto_gen_explore.plugins.meals").setLevel(config.meal_plugin_log_level())


# Create the token provider
token_provider = get_bearer_token_provider(DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/models.html#azure-openai
model_client = AzureOpenAIChatCompletionClient(
	azure_deployment=config.openai_deployment_name(),
    model="gpt-4o",
    api_version="2024-06-01",
    azure_endpoint=config.openai_endpoint(),
    azure_ad_token_provider=token_provider,  # Optional if you choose key-based authentication.
    # api_key="sk-...", # For key-based authentication.
)


lights_plugin = LightsPlugin()
meals_plugin = MealsPlugin()

# an alternative to omni_agent is to have multiple agents with a planner
planning_agent = AssistantAgent(
    name="PlanningAgent",
    model_client=model_client,
    system_message="""
    You are a planning agent.
    Your job is to break down complex tasks into smaller, manageable subtasks for other agents to perform.
    Your team members are:
        LightsAgent: Manages lights
        MealsAgent: Lists dishes, allows setting the meal time and adding dishes, and provides information on the meal preparation steps

    You only plan and delegate tasks using other agents - you do not execute them yourself.
    When listing steps, default to listing in chronological order.

    When assigning tasks, use this format:
    1. <agent> : <task>

    After all tasks are complete, summarize the findings and end with "TERMINATE".
    """,
)

lights_agent = AssistantAgent(
    name="LightsAgent",
    model_client=model_client,
    tools=[lights_plugin.get_state, lights_plugin.change_state],
    system_message="You are a helpful assistant and can manage lights.",
    reflect_on_tool_use=True,
    model_client_stream=True,  # Enable streaming tokens from the model client.
)

meals_agent = AssistantAgent(
    name="MealsAgent",
    model_client=model_client,
    tools=[meals_plugin.add_meal, meals_plugin.get_dish_options, meals_plugin.get_dishes, meals_plugin.get_meal_steps, meals_plugin.get_time_to_be_ready, meals_plugin.remove_dish, meals_plugin.set_time_to_be_ready],
    system_message="You are a helpful assistant and can manage meals using the provided tools. If a meal is added but not specified as frozen or fresh, assume fresh but ask for confirmation",
    reflect_on_tool_use=True,
    model_client_stream=True,  # Enable streaming tokens from the model client.
)

selector_prompt = """Select an agent to perform task.

{roles}

Current conversation context:
{history}

Read the above conversation, then select an agent from {participants} to perform the next task.
Make sure the planner agent has assigned tasks before other agents start working.
Only select one agent.
"""

def selector_func(messages: Sequence[AgentEvent | ChatMessage]) -> str | None:
    """Selector function to ensure the planning agent provides input after another agent has spoken."""
    if messages[-1].source != planning_agent.name:
        return planning_agent.name
    return None

text_mention_termination = TextMentionTermination("TERMINATE")
max_messages_termination = MaxMessageTermination(max_messages=25)
termination = text_mention_termination | max_messages_termination

team = SelectorGroupChat(
    [planning_agent, lights_agent, meals_agent],
    model_client=model_client,
    termination_condition=termination,
    selector_prompt=selector_prompt,
    # Allow an agent to speak multiple turns in a row.
    allow_repeated_speaker=True,
    selector_func=selector_func,
)

# add pasta, biryani and salad. show the steps to have the meal ready for 6pm

# Run the agent and stream the messages to the console.
async def main() -> None:
    # await Console(agent.run_stream(task="What is the weather in New York?"))
    while True:
        # Get the user response.
        task = input("User> ")
        if task.lower().strip() == "exit":
            break
        # Run the conversation and stream to the console.
        stream = team.run_stream(task=task)
        # Use asyncio.run(...) when running in a script.
        await Console(stream)


asyncio.run(main())