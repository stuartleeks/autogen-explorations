# from autogen_ext.models.openai import OpenAIChatCompletionClient
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
Always save figures to file in the current directory. Do not use plt.show(). All code required to complete this task must be contained within a single response.""",
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
            # e: ACADynamicSessionsCodeExecutor = self._code_executor
            # files = await e.get_file_list(cancellation_token)
            # print(f"Files: {files}")
            # downloaded_files = await e.download_files(files, cancellation_token)
            # print(f"Downloaded files: {downloaded_files}")
            await self.publish_message(Message(content=result.output), DefaultTopicId())


async def main1(): # docker executor

    work_dir = tempfile.mkdtemp()

    # Create an local embedded runtime.
    runtime = SingleThreadedAgentRuntime()

    # type: ignore[syntax]
    async with DockerCommandLineCodeExecutor(work_dir=work_dir, auto_remove=False) as executor:
        # Register the assistant and executor agents by providing
        # their agent types, the factory functions for creating instance and subscriptions.
        await Assistant.register(
            runtime,
            "assistant",
            lambda: Assistant(
                model_client
                # OpenAIChatCompletionClient(
                #     model="gpt-4o",
                #     # api_key="YOUR_API_KEY"
                # )
            ),
        )
        await Executor.register(runtime, "executor", lambda: Executor(executor))

        # Start the runtime and publish a message to the assistant.
        runtime.start()
        await runtime.publish_message(
            Message(
                "Create a plot of NVIDA vs TSLA stock returns YTD from 2024-01-01."), DefaultTopicId()
        )
        await runtime.stop_when_idle()


async def main2(): # aca ds executor

    work_dir = tempfile.mkdtemp()

    print(f"Using work_dir: {work_dir}")

    # Create an local embedded runtime.
    runtime = SingleThreadedAgentRuntime()

    executor = ACADynamicSessionsCodeExecutor(
        work_dir=work_dir,
        pool_management_endpoint=config.aca_dynamic_sessions_pool_endpoint(),
        credential=DefaultAzureCredential()
    )
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
            # "Create a plot of NVIDA vs TSLA stock returns YTD from 2024-01-01."), DefaultTopicId()
            # "Create a plot of NVIDA vs TSLA stock returns YTD from 2025-01-01."), DefaultTopicId()
            "What time is it right now?"), DefaultTopicId()
            # "List installed packages and save to packages.txt"), DefaultTopicId()
            # "what version of yfinance python package is installed?"), DefaultTopicId()
    )
    await runtime.stop_when_idle()


# asyncio.run(main1())
asyncio.run(main2())
