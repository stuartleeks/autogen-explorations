import asyncio

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
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
    system_message="Provide constructive feedback. Respond with 'APPROVE' to when your feedbacks are addressed.",
)

# Define a termination condition that stops the task if the critic approves.
text_termination = TextMentionTermination("APPROVE")

# Create a team with the primary and critic agents.
team = RoundRobinGroupChat([primary_agent, critic_agent], termination_condition=text_termination)

async def main_simple():
    result = await team.run(task="Write a short poem about the fall season.")
    print(result)

async def main_with_output():
    # When running inside a script, use a async main function and call it from `asyncio.run(...)`.
    # await team.reset()  # Reset the team for a new task.
    async for message in team.run_stream(task="Write a short poem about the fall season."):  # type: ignore
        if isinstance(message, TaskResult):
            print("Stop Reason:", message.stop_reason)
        else:
            print(message)

async def main_use_console():
    await Console(team.run_stream(task="Write a short poem about the fall season."))  # Stream the messages to the console.

async def main_external_termination():
    # Create a new team with an external termination condition.
    external_termination = ExternalTermination()
    team = RoundRobinGroupChat(
        [primary_agent, critic_agent],
        termination_condition=external_termination | text_termination,  # Use the bitwise OR operator to combine conditions.
    )

    # Run the team in a background task.
    run = asyncio.create_task(Console(team.run_stream(task="Write a short poem about the fall season.")))

    # Wait for some time.
    await asyncio.sleep(0.1)

    # Stop the team.
    external_termination.set()

    # Wait for the team to finish.
    await run

    await Console(team.run_stream())  # Resume the team to continue the last task.


async def main():
    # Create a cancellation token.
    cancellation_token = CancellationToken()

    # Use another coroutine to run the team.
    run = asyncio.create_task(
        team.run(
            task="Write a short poem about the fall season.",
            cancellation_token=cancellation_token,
        )
    )

    # Cancel the run.
    cancellation_token.cancel()

    try:
        result = await run  # This will raise a CancelledError.
    except asyncio.CancelledError:
        print("Task was cancelled.")

    print("Resuming the team...")
    await Console(team.run_stream())  # Resume the team to continue the last task.

if __name__ == "__main__":
    asyncio.run(main())
