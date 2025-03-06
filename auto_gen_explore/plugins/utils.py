from typing import AsyncGenerator, TypeVar

from autogen_agentchat.base import Response, TaskResult
from autogen_agentchat.messages import AgentEvent, ChatMessage, MultiModalMessage, TextMessage


# https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit
grey = '\x1b[38;5;8m'
yellow = '\x1b[38;5;226m'
dark_yellow = '\x1b[38;5;214m'
reset = '\x1b[0m'


T = TypeVar("T", bound=TaskResult | Response)
async def Console2(stream: AsyncGenerator[AgentEvent | ChatMessage | T, None]) -> T:
    last_processed = None
    
    async for message in stream:
        if isinstance(message, TaskResult) or isinstance(message, Response):
            last_processed = message
            continue
        # print(f"!! {message}")
        # print(f"!! {message.model_dump_json(indent=2)}")
        if message.source == "user": # skip user messages -- assume these are already displayed
            continue
        if isinstance(message, TextMessage):
            print(dark_yellow, end="", flush=True)
        else:
            print(grey, end="", flush=True)
        print(f"{'-' * 10} {message.source} {'-' * 10}", flush=True)
        if isinstance(message, MultiModalMessage):
            for c in message.content:
                print(c)
        else:
            print(message.content)
        print(reset, end="", flush=True)
        # {_message_to_str(message.chat_message, render_image_iterm=render_image_iterm)}\n"

    if last_processed is None:
        raise ValueError("No TaskResult or Response was processed.")

    return last_processed
