# from autogen_ext.models.openai import OpenAIChatCompletionClient
import base64
import json
import os
import tempfile
import asyncio
from typing import Sequence

from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from autogen_agentchat.agents import AssistantAgent, CodeExecutorAgent
from autogen_agentchat.base import TaskResult, TerminatedException, TerminationCondition
from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination
from autogen_agentchat.messages import TextMessage, AgentEvent, ChatMessage, StopMessage, MultiModalMessage
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_core import EVENT_LOGGER_NAME, CancellationToken
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


class TextContentTermination(TerminationCondition):
    """Terminate the conversation if a specific text is returned.


    Args:
        text: The text to compare the message to.
        sources: Check only messages of the specified agents for the text to look for.
    """

    def __init__(self, text: str, sources: Sequence[str] | None = None) -> None:
        self._termination_text = text
        self._terminated = False
        self._sources = sources

    @property
    def terminated(self) -> bool:
        return self._terminated

    async def __call__(self, messages: Sequence[AgentEvent | ChatMessage]) -> StopMessage | None:
        if self._terminated:
            raise TerminatedException(
                "Termination condition has already been reached")
        for message in messages:
            if self._sources is not None and message.source not in self._sources:
                continue

            if isinstance(message.content, str) and self._termination_text == message.content:
                self._terminated = True
                return StopMessage(
                    content=f"Text '{self._termination_text}' mentioned", source="TextMentionTermination"
                )
            elif isinstance(message, MultiModalMessage):
                for item in message.content:
                    if isinstance(item, str) and self._termination_text == item:
                        self._terminated = True
                        return StopMessage(
                            content=f"Text '{self._termination_text}' mentioned", source="TextMentionTermination"
                        )
        return None

    async def reset(self) -> None:
        self._terminated = False



def temp_dir():
    """Create a temporary directory for the work_dir under temp_dir in the current folder ."""

    # Get the current working directory
    current_dir = os.getcwd()

    # Create the temp_dir path
    temp_dir = os.path.join(current_dir, "temp_dir")

    # Create the temp_dir if it doesn't exist
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    return tempfile.TemporaryDirectory(dir=temp_dir)


async def main():

    cancellation_token = CancellationToken()

    # with tempfile.TemporaryDirectory() as work_dir:
    with temp_dir() as work_dir:
        print(f"Using work_dir: {work_dir}")

        code_agent = AssistantAgent(
            "code_agent",
            model_client=model_client,
            system_message="""Write Python script in markdown block, and it will be executed.
        Prefer outputting to the console but save images to a file in the current directory. Do not use plt.show(). All code required to complete this task must be contained within a single response.

    You have a data file named 'batches.csv' in the current directory. It contains data about batches of ingregients. The columns are:
    - id: The ID of the batch.
    - description: A description of the batch contents
    - source_batches: A comma separated list of batch IDs used to manufacture this batch (not including the time for the source batch manufacturing).
    - time: the number of days it takes to manufacture this batch.

    Each batch can be manufactured from other batches. For example, batch 1 might be manufactured from batches 2 and 3. The time to manufacture a batch is the sum of the time to manufacture each of its source batches.

    End batches (or result batches) are those that are not used in the manufacture of other batches.

    Don't include the file content in the response.

    List output to the console unless directed to save to a file."""
            "Do not include 'TERMINATE' in the generated code."
            "Reply only 'TERMINATE' if the task is done."
            # "Transfer to the user agent after performing the requested actions.",

        )
        
        executor = ACADynamicSessionsCodeExecutor(
            work_dir=work_dir,
            pool_management_endpoint=config.aca_dynamic_sessions_pool_endpoint(),
            credential=DefaultAzureCredential(),
            # suppress_result_output=True,
        )
        # Get the path to batches.csv file (in the same directory as this script)
        batches_path = os.path.join(os.path.dirname(__file__), "batches.csv")
        await executor.upload_files([batches_path], cancellation_token=cancellation_token)

        executor_agent = CodeExecutorAgent(
            "executor_agent", code_executor=executor)

        # termination = TextMentionTermination("TERMINATE") | MaxMessageTermination(10)
        termination = TextContentTermination("TERMINATE") | MaxMessageTermination(10)
        team = RoundRobinGroupChat(
            participants=[code_agent, executor_agent],
            termination_condition=termination,
        )

        while True:
            user_message = input("User (type 'exit' to close the session): ")
            # user_message = "plot the batches by manufacturing time"
            if user_message.strip().lower() == "exit":
                return
            # task_result = await Console(team.run_stream(task=user_message))

            result = None
            async for message in team.run_stream(task=user_message):
                print("-" * 80)
                print(f"Message: {message}")
                if isinstance(message, TaskResult):
                    result = message
                else:
                    if message.source == "executor_agent":
                        try:
                            json_content = json.loads(message.content)
                            print(f"Parsed JSON content: {json_content}")
                            if "type" in json_content and json_content["type"] == "image":
                                # lazy - assuming format and base64_data are present!
                                format = json_content["format"]
                                base64_data = json_content["base64_data"]
                                # decode and save the content to file
                                image_data = base64.b64decode(base64_data)
                                image_path = os.path.join(
                                    work_dir, f"image.{format}")
                                with open(image_path, "wb") as image_file:
                                    image_file.write(image_data)
                                print(f"Image saved to {image_path}")
                        except Exception as e:
                            print(f"Error parsing message: {e}")
                            
                        print(f"ExecutorAgent: {message.content}")
                        files = await executor.get_file_list(cancellation_token)
                        print(f"Files: {files}")
                        downloaded_files = await executor.download_files(files, cancellation_token)
                        print(f"Downloaded files: {downloaded_files}")

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
