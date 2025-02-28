import asyncio
import logging
from typing import Sequence

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from autogen_core.model_context import BufferedChatCompletionContext
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


from autogen_agentchat.agents import AssistantAgent, UserProxyAgent
from autogen_agentchat.messages import AgentEvent, ChatMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_agentchat.base import TaskResult
from autogen_core import CancellationToken

from autogen_agentchat.conditions import ExternalTermination, TextMentionTermination

# Create the token provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/models.html#azure-openai
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment=config.openai_deployment_name(),
    model="gpt-4o",
    api_version="2024-06-01",
    azure_endpoint=config.openai_endpoint(),
    # Optional if you choose key-based authentication.
    azure_ad_token_provider=token_provider,
    # api_key="sk-...", # For key-based authentication.
)

assistant = AssistantAgent("assistant", model_client=model_client)
def user_input(prompt: str) -> str:
    return input(prompt + "\n> ")

user_proxy = UserProxyAgent("user_proxy", input_func=user_input)  # Use input() to get user input from console.

# Create the termination condition which will end the conversation when the user says "APPROVE".
termination = TextMentionTermination("APPROVE")



async def main():
    # Create the team.
    team = RoundRobinGroupChat([assistant, user_proxy], termination_condition=termination)

    # Run the conversation and stream to the console.
    stream = team.run_stream(task="Write a 4-line poem about the ocean.")
    # Use asyncio.run(...) when running in a script.
    await Console(stream)


async def main_feedback_between_runs():

    # Create the team setting a maximum number of turns to 1.
    team = RoundRobinGroupChat([assistant], max_turns=1)

    task = "Write a 4-line poem about the ocean."
    while True:
        # Run the conversation and stream to the console.
        stream = team.run_stream(task=task)
        # Use asyncio.run(...) when running in a script.
        await Console(stream)
        # Get the user response.
        task = input("Enter your feedback (type 'exit' to leave): ")
        if task.lower().strip() == "exit":
            break

if __name__ == "__main__":
    asyncio.run(main_feedback_between_runs())

