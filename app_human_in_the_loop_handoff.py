import asyncio

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_agentchat.base import Handoff

from autogen_agentchat.conditions import TextMentionTermination, HandoffTermination

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


# Create a lazy assistant agent that always hands off to the user.
lazy_agent = AssistantAgent(
    "lazy_assistant",
    model_client=model_client,
    handoffs=[Handoff(target="user", message="Transfer to user.")],
    system_message="If you cannot complete the task, transfer to user. Otherwise, when finished, respond with 'TERMINATE'.",
)

# Define a termination condition that checks for handoff messages.
handoff_termination = HandoffTermination(target="user")
# Define a termination condition that checks for a specific text mention.
text_termination = TextMentionTermination("TERMINATE")

# Create a single-agent team with the lazy assistant and both termination conditions.
lazy_agent_team = RoundRobinGroupChat([lazy_agent], termination_condition=handoff_termination | text_termination)


async def main():
    # Run the team and stream to the console.
    task = "What is the weather in New York?"
    await Console(lazy_agent_team.run_stream(task=task), output_stats=True)

    await Console(lazy_agent_team.run_stream(task="The weather in New York is sunny."))

if __name__ == "__main__":
    asyncio.run(main())

