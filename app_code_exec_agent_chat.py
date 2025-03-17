# from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.code_executors.azure import ACADynamicSessionsCodeExecutor
from autogen_core import SingleThreadedAgentRuntime
import tempfile
import asyncio
import re
from dataclasses import dataclass
from typing import List

from autogen_core import DefaultTopicId, MessageContext, RoutedAgent, default_subscription, message_handler
from autogen_core.code_executor import CodeBlock, CodeExecutor
from autogen_core.models import (
    AssistantMessage,
    ChatCompletionClient,
    LLMMessage,
    SystemMessage,
    UserMessage,
)
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient


import asyncio
import logging
from autogen_ext.models.openai import (AzureOpenAIChatCompletionClient)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from typing import Sequence

from autogen_agentchat.agents import AssistantAgent, CodeExecutorAgent
from autogen_agentchat.conditions import HandoffTermination
from autogen_agentchat.base import TerminationCondition, TerminatedException
from autogen_agentchat.messages import HandoffMessage, AgentEvent, ChatMessage, StopMessage, TextMessage
from autogen_agentchat.teams import Swarm, RoundRobinGroupChat, SelectorGroupChat
from autogen_agentchat.ui import Console
from auto_gen_explore import config
from auto_gen_explore.plugins.lights import LightsPlugin
from auto_gen_explore.plugins.meals import MealsPlugin

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


# https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/code-execution-groupchat.html

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

selector_prompt = """Select an agent to perform task.

{roles}

Current conversation context:
{history}

Read the above conversation, then select an agent from {participants} to perform the next task.
Make sure the planner agent has assigned tasks before other agents start working.
Only select one agent.
"""

async def main():

    with tempfile.TemporaryDirectory() as work_dir:
        print(f"Using work_dir: {work_dir}")

        # Create an local embedded runtime.
        runtime = SingleThreadedAgentRuntime()


        code_agent = AssistantAgent(
            "code_agent",
            model_client=model_client,
            system_message="""Write Python script in markdown block, and it will be executed.
        Always save figures to file in the current directory. Do not use plt.show(). All code required to complete this task must be contained within a single response.""",
            handoffs=["executor_agent", "user"],
            reflect_on_tool_use=False,
        )

        executor = ACADynamicSessionsCodeExecutor(
            work_dir=work_dir,
            pool_management_endpoint=config.aca_dynamic_sessions_pool_endpoint(),
            credential=DefaultAzureCredential()
        )
        executor_agent = CodeExecutorAgent("executor_agent", code_executor=executor)

        termination=HandoffTermination(target="user")
        # termination=HandoffTermination(target="user") | AgentTextMessageTermination()
        # team=Swarm(
        team=SelectorGroupChat(
            participants=[code_agent, executor_agent],
            termination_condition=termination,
            selector_prompt=selector_prompt,
            model_client=model_client,
        )

        user_message=input("User (type 'exit' to close the session): ")
        if user_message.strip().lower() == "exit":
            return
        task_result=await Console(team.run_stream(task=user_message))
        last_message=task_result.messages[-1]

        while isinstance(last_message, HandoffMessage) and last_message.target == "user": # use this normally (i.e. not using AgentTextMessageTermination)
        # while True: # use this if using AgentTextMessageTermination
            user_message=input("User (type 'exit' to close the session): ")
            if user_message.strip().lower() == "exit":
                return

            task_result=await Console(
                team.run_stream(task=HandoffMessage(
                    source="user", target=last_message.source, content=user_message))
            )
            last_message=task_result.messages[-1]

asyncio.run(main())
