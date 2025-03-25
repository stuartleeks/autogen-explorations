# from autogen_ext.models.openai import OpenAIChatCompletionClient
import tempfile
import asyncio

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from autogen_agentchat.agents import AssistantAgent, CodeExecutorAgent
from autogen_agentchat.base import TaskResult
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import TextMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_core import EVENT_LOGGER_NAME
from autogen_ext.code_executors.azure import ACADynamicSessionsCodeExecutor
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient

from auto_gen_explore import config

import logging


logging.basicConfig()

# # logging.getLogger("httpx").setLevel(logging.INFO) # useful to see the URLs used (e.g. when debugging a 404 for AOAI)
# logging.getLogger("kernel").setLevel(config.semantic_kernel_log_level())
# logging.getLogger("AIAgent").setLevel(config.agent_log_level())

# logger = logging.getLogger(EVENT_LOGGER_NAME).setLevel(logging.INFO) # look for type=LLMCall to see model calls


# https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/code-execution-groupchat.html

# Create the token provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/models.html#azure-openai
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment=config.openai_deployment_name(),
    model="gpt-4o-2024-11-20",
    api_version="2024-06-01",
    azure_endpoint=config.openai_endpoint(),
    # Optional if you choose key-based authentication.
    azure_ad_token_provider=token_provider,
    # api_key="sk-...", # For key-based authentication.
)




async def main():

    with tempfile.TemporaryDirectory() as work_dir:
        print(f"Using work_dir: {work_dir}")

        code_agent = AssistantAgent(
            "code_agent",
            model_client=model_client,
            system_message="""Write Python script in markdown block, and it will be executed.
        Prefer outputting to the console but save images to a file in the current directory. Do not use plt.show(). All code required to complete this task must be contained within a single response.
        Reply only 'TERMINATE' if the task is done.""",
        )

        executor = ACADynamicSessionsCodeExecutor(
            work_dir=work_dir,
            pool_management_endpoint=config.aca_dynamic_sessions_pool_endpoint(),
            credential=DefaultAzureCredential()
        )
        executor_agent = CodeExecutorAgent(
            "executor_agent", code_executor=executor)

        termination = TextMentionTermination(
            "TERMINATE") | MaxMessageTermination(10)
        team = RoundRobinGroupChat(
            participants=[code_agent, executor_agent],
            termination_condition=termination,
        )

        user_message = input("User (type 'exit' to close the session): ")
        if user_message.strip().lower() == "exit":
            return
        # task_result = await Console(team.run_stream(task=user_message))

        result = None
        async for message in team.run_stream(task=user_message):
            print("-" * 80)
            print(f"Message: {message}")

            if isinstance(message, TaskResult):
                result = message

        token_count = 0
        message_summaries = []
        output = ""
        for message in result.messages:
            if isinstance(message, TextMessage):
                message_summaries.append(
                    f"{message.source}: {message.content}")
                if message.source == "executor_agent":
                    output = message.content
                if message.models_usage:
                    token_count += message.models_usage.completion_tokens + \
                        message.models_usage.prompt_tokens

        result = {
            "messages": message_summaries,
            "total_tokens": token_count,
            "human_input": user_message,
            "output": output,
        }
        print(f"Result: {result}")

asyncio.run(main())
