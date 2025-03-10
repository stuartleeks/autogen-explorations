import asyncio
import json
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider


from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import HandoffTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_ext.models.openai import (AzureOpenAIChatCompletionClient)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import MaxMessageTermination
from autogen_agentchat.teams import RoundRobinGroupChat, Swarm
from autogen_agentchat.ui import Console

from auto_gen_explore import config

# Testing the serialization of the state of the team and swarm as part of tracking down an error
# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/state.html#saving-and-loading-teams


# Create the token provider
api_key = config.openai_key_if_set()
if api_key:
    token_provider = None
else:
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")
    
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment=config.openai_deployment_name(),
    model=config.openai_model_name(),
    api_version=config.openai_api_version(),
    azure_endpoint=config.openai_endpoint(),
    azure_ad_token_provider=token_provider,
    api_key=api_key,
)


async def main1():
    # Define a team.
    assistant_agent = AssistantAgent(
        name="assistant_agent",
        system_message="You are a helpful assistant",
        model_client=model_client,
    )
    agent_team = RoundRobinGroupChat([assistant_agent], termination_condition=MaxMessageTermination(max_messages=2))

    # Run the team and stream messages to the console.
    stream = agent_team.run_stream(task="Write a beautiful poem 3-line about lake tangayika")

    # Use asyncio.run(...) when running in a script.
    await Console(stream)

    team_state = await agent_team.save_state()
     
    with open(".team_state.json", "w") as f:
        json.dump(team_state, f)


async def main2():
    # Define a team.
    assistant_agent = AssistantAgent(
        name="assistant_agent",
        system_message="You are a helpful assistant",
        model_client=model_client,
        handoffs=["poetry_agent"]
    )
    poetry_agent = AssistantAgent(
        name="poetry_agent",
        system_message="You are a poetry assistant. Transfer to user when you are done.",
        model_client=model_client,
        handoffs=["user"]
    )
    termination = MaxMessageTermination(max_messages=4) | HandoffTermination(target="user")
    swarm = Swarm([assistant_agent, poetry_agent], termination_condition=termination)

    # Run the team and stream messages to the console.
    stream = swarm.run_stream(task="Write a beautiful poem 3-line about lake tangayika")

    # Use asyncio.run(...) when running in a script.
    await Console(stream)

    swarm_state = await swarm.save_state()
    print()
    print(swarm_state)
     
    # print(json.dumps(swarm_state, indent=2))
    with open(".swarm_state.json", "w") as f:
        json.dump(swarm_state, f)



# asyncio.run(main1())
# print("################################")
# print("################################")
# print("################################")
# print("################################")
asyncio.run(main2())
