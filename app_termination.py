import asyncio

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console

from autogen_agentchat.conditions import MaxMessageTermination, TextMentionTermination

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

# Create the primary agent.
primary_agent = AssistantAgent(
    "primary",
    model_client=model_client,
    system_message="You are a helpful AI assistant.",
)

# Create the critic agent.
critic_agent = AssistantAgent(
    "critic",
    model_client=model_client,
    system_message="Provide constructive feedback for every message. Respond with 'APPROVE' to when your feedbacks are addressed.",
)

# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/termination.html

async def main():
    max_msg_termination = MaxMessageTermination(max_messages=3)
    round_robin_team = RoundRobinGroupChat([primary_agent, critic_agent], termination_condition=max_msg_termination)
    await Console(round_robin_team.run_stream(task="Write a unique, Haiku about the weather in Paris"))

    # Continue to allow primary agent to respond
    await Console(round_robin_team.run_stream())

async def main_feedback_between_runs():
    # combine termination conditions (max messages and text mention)
    max_msg_termination = MaxMessageTermination(max_messages=10)
    text_termination = TextMentionTermination("APPROVE")
    combined_termination = max_msg_termination | text_termination
    round_robin_team = RoundRobinGroupChat([primary_agent, critic_agent], termination_condition=combined_termination)

    await Console(round_robin_team.run_stream(task="Write a unique, Haiku about the weather in Paris"))


if __name__ == "__main__":
    asyncio.run(main_feedback_between_runs())

