# from autogen_ext.models.openai import OpenAIChatCompletionClient
import os
from autogen_ext.code_executors.docker import DockerCommandLineCodeExecutor
from autogen_ext.code_executors.azure import ACADynamicSessionsCodeExecutor
from autogen_core import CancellationToken, SingleThreadedAgentRuntime
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


from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config


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

cancellation_token = CancellationToken()


@dataclass
class Message:
    content: str


@default_subscription
class Assistant(RoutedAgent):
    def __init__(self, model_client: ChatCompletionClient) -> None:
        super().__init__("An assistant agent.")
        self._model_client = model_client
        self._chat_history: List[LLMMessage] = [
            SystemMessage(
                content="""Write Python script in markdown block, and it will be executed.
Always save figures to file in the current directory. Do not use plt.show(). All code required to complete this task must be contained within a single response.

    You have a data file named 'batches.csv' in the current directory. It contains data about batches of ingregients. The columns are:
    - id: The ID of the batch.
    - description: A description of the batch contents
    - source_batches: A comma separated list of batch IDs used to manufacture this batch (not including the time for the source batch manufacturing).
    - time: the number of days it takes to manufacture this batch.

    Each batch can be manufactured from other batches. For example, batch 1 might be manufactured from batches 2 and 3. The time to manufacture a batch is the sum of the time to manufacture each of its source batches.

    End batches (or result batches) are those that are not used in the manufacture of other batches.

    List output to the console unless directed to save to a file.
""",
            )
        ]

    @message_handler
    async def handle_message(self, message: Message, ctx: MessageContext) -> None:
        self._chat_history.append(UserMessage(
            content=message.content, source="user"))
        result = await self._model_client.create(self._chat_history)
        print(f"\n{'-'*80}\nAssistant:\n{result.content}")
        self._chat_history.append(AssistantMessage(
            content=result.content, source="assistant"))  # type: ignore
        # type: ignore
        await self.publish_message(Message(content=result.content), DefaultTopicId())


def extract_markdown_code_blocks(markdown_text: str) -> List[CodeBlock]:
    pattern = re.compile(r"```(?:\s*([\w\+\-]+))?\n([\s\S]*?)```")
    matches = pattern.findall(markdown_text)
    code_blocks: List[CodeBlock] = []
    for match in matches:
        language = match[0].strip() if match[0] else ""
        code_content = match[1]
        code_blocks.append(CodeBlock(code=code_content, language=language))
    return code_blocks


@default_subscription
class Executor(RoutedAgent):
    def __init__(self, code_executor: CodeExecutor) -> None:
        super().__init__("An executor agent.")
        self._code_executor = code_executor

    @message_handler
    async def handle_message(self, message: Message, ctx: MessageContext) -> None:
        code_blocks = extract_markdown_code_blocks(message.content)
        # print(code_blocks)
        if code_blocks:
            result = await self._code_executor.execute_code_blocks(
                code_blocks, cancellation_token=ctx.cancellation_token
            )
            print(f"\n{'-'*80}\nExecutor:\n{result.output}")
            
            e: ACADynamicSessionsCodeExecutor = self._code_executor
            files = await e.get_file_list(cancellation_token)
            print(f"Files: {files}")
            downloaded_files = await e.download_files(files, cancellation_token)
            print(f"Downloaded files: {downloaded_files}")
            
            await self.publish_message(Message(content=result.output), DefaultTopicId())

def make_temp_dir():
    """Create a temporary directory for the work_dir under temp_dir in the current folder ."""
    
    # Get the current working directory
    current_dir = os.getcwd()

    # Create the temp_dir path
    temp_dir = os.path.join(current_dir, "temp_dir")

    # Create the temp_dir if it doesn't exist
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)

    # Create a temporary directory under temp_dir
    work_dir = tempfile.mkdtemp(dir=temp_dir)
    return work_dir


async def main(): # aca ds executor

    # work_dir = tempfile.mkdtemp()
    work_dir = make_temp_dir()

    print(f"Using work_dir: {work_dir}")

    # Create an local embedded runtime.
    runtime = SingleThreadedAgentRuntime()

    executor = ACADynamicSessionsCodeExecutor(
        work_dir=work_dir,
        pool_management_endpoint=config.aca_dynamic_sessions_pool_endpoint(),
        credential=DefaultAzureCredential()
    )
    # Get the path to batches.csv file (in the same directory as this script)
    batches_path = os.path.join(os.path.dirname(__file__), "batches.csv")
    await executor.upload_files([batches_path],cancellation_token=cancellation_token)

    # Register the assistant and executor agents by providing
    # their agent types, the factory functions for creating instance and subscriptions.
    await Assistant.register(
        runtime,
        "assistant",
        lambda: Assistant(
            model_client
        ),
    )
    await Executor.register(runtime, "executor", lambda: Executor(executor))

    # Start the runtime and publish a message to the assistant.
    runtime.start()
    await runtime.publish_message(
        Message(
            # "Show the total time to manufacture each batch"), DefaultTopicId()
            # "Show the total time to manufacture each end batch"), DefaultTopicId()
            # "Determine which batches would have the biggest impact on the end batch manufacturing time if they were delayed"), DefaultTopicId()
            # "Determine which batches would have the biggest impact on the end batch manufacturing time if they were delayed. Plot the top five batches on a bar chart."), DefaultTopicId()
            "Determine which batches would have the biggest impact on the end batch manufacturing time if they were delayed. Plot the top five batches on a bar chart using the description as the batch label."), DefaultTopicId()
    )
    await runtime.stop_when_idle()


asyncio.run(main())
