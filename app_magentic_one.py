# from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.code_executors.azure import ACADynamicSessionsCodeExecutor
from autogen_core import SingleThreadedAgentRuntime
import tempfile
import asyncio
import re
from dataclasses import dataclass
from typing import List

from autogen_ext.models.openai import OpenAIChatCompletionClient
from autogen_ext.teams.magentic_one import MagenticOne
from autogen_agentchat.ui import Console
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


from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


# https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/code-execution-groupchat.html

# Create the token provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

POOL_MANAGEMENT_ENDPOINT = config.aca_dynamic_sessions_pool_endpoint()


# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/models.html#azure-openai
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment=config.openai_deployment_name(),
    # model="gpt-4o",
    model="gpt-4o-2024-11-20",
    api_version="2024-06-01",
    azure_endpoint=config.openai_endpoint(),
    # Optional if you choose key-based authentication.
    azure_ad_token_provider=token_provider,
    # api_key="sk-...", # For key-based authentication.
)



async def example_usage():
    with tempfile.TemporaryDirectory() as temp_dir:
        # executor = DockerCommandLineCodeExecutor()
        executor = ACADynamicSessionsCodeExecutor(
            pool_management_endpoint=POOL_MANAGEMENT_ENDPOINT, credential=DefaultAzureCredential(), work_dir=temp_dir
        )
        m1 = MagenticOne(client=model_client, code_executor=executor)
        # task = "Write a Python script to fetch data from an API."
        # task = "Find the class times for Purple Salsa tonight."
        task = "What python packages are installed?"
        result = await Console(m1.run_stream(task=task))
        # print(result)


if __name__ == "__main__":
    asyncio.run(example_usage())

