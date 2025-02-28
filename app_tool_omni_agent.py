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

# omni_agent is fed with all the tools
omni_agent = AssistantAgent(
    name="lights_agent",
    model_client=model_client,
    tools=[lights_plugin.get_state, lights_plugin.change_state,
           meals_plugin.add_meal, meals_plugin.get_dish_options, meals_plugin.get_dishes, meals_plugin.get_meal_steps, meals_plugin.get_time_to_be_ready, meals_plugin.remove_dish, meals_plugin.set_time_to_be_ready],
    system_message="You are a helpful assistant.",
    # system_message="You are a bot. Use tools where possible and communicate tool use to the user.",
    reflect_on_tool_use=True,
    model_context=BufferedChatCompletionContext(buffer_size=5),
    model_client_stream=True,  # Enable streaming tokens from the model client.
)

# Run the agent and stream the messages to the console.
async def main() -> None:
    # await Console(agent.run_stream(task="What is the weather in New York?"))
    while True:
        # Get the user response.
        task = input("User> ")
        if task.lower().strip() == "exit":
            break
        # Run the conversation and stream to the console.
        stream = omni_agent.run_stream(task=task)
        # Use asyncio.run(...) when running in a script.
        await Console(stream)


asyncio.run(main())