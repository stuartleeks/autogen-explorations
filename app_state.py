import asyncio

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console

from autogen_agentchat.conditions import MaxMessageTermination

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
# Define a team.
assistant_agent = AssistantAgent(
    name="assistant_agent",
    system_message="You are a helpful assistant",
    model_client=model_client,
)
agent_team = RoundRobinGroupChat([assistant_agent], termination_condition=MaxMessageTermination(max_messages=2))


# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/state.html

async def main():
    # Run the team and stream messages to the console.
    stream = agent_team.run_stream(task="Write a beautiful poem 3-line about lake tangayika")

    # Use asyncio.run(...) when running in a script.
    await Console(stream)

    # Save the state of the agent team.
    team_state = await agent_team.save_state()
    print(team_state)

    print("")
    print("!!! Reset and run again...")
    await agent_team.reset() # set to fresh state (simulate new request in web api etc)
    stream = agent_team.run_stream(task="What was the last line of the poem you wrote?")
    await Console(stream)

    # Load team state.
    print("")
    print("!!! Load previous state and retry...")
    await agent_team.load_state(team_state)
    stream = agent_team.run_stream(task="What was the last line of the poem you wrote?")
    await Console(stream)

if __name__ == "__main__":
    asyncio.run(main())

