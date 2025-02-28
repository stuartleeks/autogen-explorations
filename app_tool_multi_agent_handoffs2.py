import asyncio
import json
import logging
import uuid
from typing import List, Sequence, Tuple

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import (MaxMessageTermination,
                                          TextMentionTermination)
from autogen_agentchat.messages import AgentEvent, ChatMessage
from autogen_agentchat.teams import SelectorGroupChat
from autogen_agentchat.ui import Console
from autogen_core.model_context import BufferedChatCompletionContext
from autogen_core.tools import FunctionTool, Tool
from autogen_ext.models.openai import (AzureOpenAIChatCompletionClient,
                                       OpenAIChatCompletionClient)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from pydantic import BaseModel

from auto_gen_explore import config
from auto_gen_explore.plugins.lights import LightsPlugin
from auto_gen_explore.plugins.meals import MealsPlugin

from autogen_core import (FunctionCall, MessageContext, RoutedAgent,
                          SingleThreadedAgentRuntime, TopicId,
                          TypeSubscription, message_handler)
from autogen_core.models import (AssistantMessage, ChatCompletionClient,
                                 FunctionExecutionResult,
                                 FunctionExecutionResultMessage, LLMMessage,
                                 SystemMessage, UserMessage)

##https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit
grey = '\x1b[38;5;8m'
yellow = '\x1b[38;5;226m'
dark_yellow = '\x1b[38;5;214m'
reset = '\x1b[0m'


logging.basicConfig(
    # format="[%(asctime)s - %(name)s:%(lineno)d - %(levelname)s] %(message)s",
    format=f"{grey}%(message)s{reset}",
    datefmt="%Y-%m-%d %H:%M:%S",
    # level=logging.DEBUG
)

# logging.getLogger("httpx").setLevel(logging.INFO) # useful to see the URLs used (e.g. when debugging a 404 for AOAI)
logging.getLogger("kernel").setLevel(config.semantic_kernel_log_level())
logging.getLogger("AIAgent").setLevel(config.agent_log_level())

# Create the token provider
token_provider = get_bearer_token_provider(
    DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/models.html#azure-openai
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment=config.openai_deployment_name(),
    model=config.openai_model_name(),
    api_version=config.openai_api_version(),
    azure_endpoint=config.openai_endpoint(),
    # Optional if you choose key-based authentication.
    azure_ad_token_provider=token_provider,
    # api_key="sk-...", # For key-based authentication.
)

# Messages for agent communication


class UserLogin(BaseModel):
    pass


class UserTask(BaseModel):
    context: List[LLMMessage]


class AgentResponse(BaseModel):
    reply_to_topic_type: str
    context: List[LLMMessage]


# AI Agent
# https://microsoft.github.io/autogen/stable/user-guide/core-user-guide/design-patterns/handoffs.html
class AIAgent(RoutedAgent):
    def __init__(
        self,
        description: str,
        system_message: SystemMessage,
        model_client: ChatCompletionClient,
        tools: List[Tool],
        delegate_tools: List[Tool],
        agent_topic_type: str,
        user_topic_type: str,
    ) -> None:
        super().__init__(description)
        self._logger = logging.getLogger(self.__class__.__name__)
        self._system_message = system_message
        self._model_client = model_client
        self._tools = dict([(tool.name, tool) for tool in tools])
        self._tool_schema = [tool.schema for tool in tools]
        self._delegate_tools = dict([(tool.name, tool)
                                    for tool in delegate_tools])
        self._delegate_tool_schema = [tool.schema for tool in delegate_tools]
        self._agent_topic_type = agent_topic_type
        self._user_topic_type = user_topic_type

    @message_handler
    async def handle_task(self, message: UserTask, ctx: MessageContext) -> None:
        # Send the task to the LLM.
        llm_result = await self._model_client.create(
            messages=[self._system_message] + message.context,
            tools=self._tool_schema + self._delegate_tool_schema,
            cancellation_token=ctx.cancellation_token,
        )
        self._logger.debug(f"{'-'*80}\n{self.id.type}:\n{llm_result.content}")
        # Process the LLM result.
        while isinstance(llm_result.content, list) and all(isinstance(m, FunctionCall) for m in llm_result.content):
            tool_call_results: List[FunctionExecutionResult] = []
            delegate_targets: List[Tuple[str, UserTask]] = []
            # Process each function call.
            for call in llm_result.content:
                arguments = json.loads(call.arguments)
                if call.name in self._tools:
                    # Execute the tool directly.
                    result = await self._tools[call.name].run_json(arguments, ctx.cancellation_token)
                    result_as_str = self._tools[call.name].return_value_as_string(
                        result)
                    tool_call_results.append(
                        FunctionExecutionResult(
                            call_id=call.id, content=result_as_str, is_error=False)
                    )
                elif call.name in self._delegate_tools:
                    # Execute the tool to get the delegate agent's topic type.
                    result = await self._delegate_tools[call.name].run_json(arguments, ctx.cancellation_token)
                    topic_type = self._delegate_tools[call.name].return_value_as_string(
                        result)
                    # Create the context for the delegate agent, including the function call and the result.
                    delegate_messages = list(message.context) + [
                        AssistantMessage(content=[call], source=self.id.type),
                        FunctionExecutionResultMessage(
                            content=[
                                FunctionExecutionResult(
                                    call_id=call.id,
                                    content=f"Transferred to {topic_type}. Adopt persona immediately.",
                                    is_error=False,
                                )
                            ]
                        ),
                    ]
                    delegate_targets.append(
                        (topic_type, UserTask(context=delegate_messages)))
                else:
                    raise ValueError(f"Unknown tool: {call.name}")
            if len(delegate_targets) > 0:
                # Delegate the task to other agents by publishing messages to the corresponding topics.
                for topic_type, task in delegate_targets:
                    self._logger.debug(
                        f"{'-'*80}\n{self.id.type}:\nDelegating to {topic_type}")
                    await self.publish_message(task, topic_id=TopicId(topic_type, source=self.id.key))
            if len(tool_call_results) > 0:
                self._logger.debug(f"{'-'*80}\n{self.id.type}:\n{tool_call_results}")
                # Make another LLM call with the results.
                message.context.extend(
                    [
                        AssistantMessage(
                            content=llm_result.content, source=self.id.type),
                        FunctionExecutionResultMessage(
                            content=tool_call_results),
                    ]
                )
                llm_result = await self._model_client.create(
                    messages=[self._system_message] + message.context,
                    tools=self._tool_schema + self._delegate_tool_schema,
                    cancellation_token=ctx.cancellation_token,
                )
                self._logger.debug(f"{'-'*80}\n{self.id.type}:\n{llm_result.content}")
            else:
                # The task has been delegated, so we are done.
                return
        # The task has been completed, publish the final result.
        assert isinstance(llm_result.content, str)
        message.context.append(AssistantMessage(
            content=llm_result.content, source=self.id.type))
        await self.publish_message(
            AgentResponse(context=message.context,
                          reply_to_topic_type=self._agent_topic_type),
            topic_id=TopicId(self._user_topic_type, source=self.id.key),
        )


class UserAgent(RoutedAgent):
    def __init__(self, description: str, user_topic_type: str, agent_topic_type: str) -> None:
        super().__init__(description)
        self._user_topic_type = user_topic_type
        self._agent_topic_type = agent_topic_type

    @message_handler
    async def handle_user_login(self, message: UserLogin, ctx: MessageContext) -> None:
        print(f"{'-'*80}\n{yellow}User login, session ID: {self.id.key}.{reset}", flush=True)
        # Get the user's initial input after login.
        user_input = input(f"{yellow}User: {reset}")
        # print(f"{'-'*80}\n{self.id.type}:\n{user_input}")
        await self.publish_message(
            UserTask(context=[UserMessage(content=user_input, source="User")]),
            topic_id=TopicId(self._agent_topic_type, source=self.id.key),
        )

    @message_handler
    async def handle_task_result(self, message: AgentResponse, ctx: MessageContext) -> None:
        # Get the user's input after receiving a response from an agent.
        last_agent_message = message.context[-1].content
        print(f"{dark_yellow}{last_agent_message}{reset}", flush=True)
        user_input = input(f"{yellow}User (type 'exit' to close the session): {reset}")
        # print(f"{'-'*80}\n{self.id.type}:\n{user_input}", flush=True)
        if user_input.strip().lower() == "exit":
            print(f"{'-'*80}\nUser session ended, session ID: {self.id.key}.")
            return
        message.context.append(UserMessage(content=user_input, source="User"))
        await self.publish_message(
            UserTask(context=message.context), topic_id=TopicId(message.reply_to_topic_type, source=self.id.key)
        )



lights_agent_topic_type = "LightsAgent"
meals_agent_topic_type = "MealsAgent"
triage_agent_topic_type = "TriageAgent"
user_topic_type = "User"


def transfer_to_lights_agent() -> str:
    return lights_agent_topic_type


def transfer_to_meals() -> str:
    return meals_agent_topic_type


def transfer_back_to_triage() -> str:
    return triage_agent_topic_type


transfer_to_lights_tool = FunctionTool(
    transfer_to_lights_agent, description="Use for anything lighting related."
)
transfer_to_meals_tool = FunctionTool(
    transfer_to_meals, description="Use for anything meal related."
)
transfer_back_to_triage_tool = FunctionTool(
    transfer_back_to_triage,
    description="Call this if the user brings up a topic outside of your purview,\nincluding escalating to human.",
)


lights_plugin = LightsPlugin()
meals_plugin = MealsPlugin()


# create the team

async def main():
    runtime = SingleThreadedAgentRuntime()

    # Register the triage agent.
    triage_agent_type = await AIAgent.register(
        runtime,
        # Using the topic type as the agent type.
        type=triage_agent_topic_type,
        factory=lambda: AIAgent(
            description="A triage agent.",
            system_message=SystemMessage(
                content="You are a bot to help users. "
                "Introduce yourself. Always be very brief. "
                "For food related questions, transfer to the meals agent. "
                "Gather information to direct the customer to the right agent."
                "But make your questions subtle and natural."
            ),
            model_client=model_client,
            tools=[],
            delegate_tools=[
                transfer_to_meals_tool,
                transfer_to_lights_tool,
            ],
            agent_topic_type=triage_agent_topic_type,
            user_topic_type=user_topic_type,
        ),
    )
    # Add subscriptions for the triage agent: it will receive messages published to its own topic only.
    await runtime.add_subscription(TypeSubscription(topic_type=triage_agent_topic_type, agent_type=triage_agent_type.type))

    # Register the lights agent.
    lights_agent_type = await AIAgent.register(
        runtime,
        # Using the topic type as the agent type.
        type=lights_agent_topic_type,
        factory=lambda: AIAgent(
            description="A lights agent.",
            system_message=SystemMessage(
                content="You are a an agent that can provide information on the status of lights and turn lights on and off"
                "Always answer in a sentence or less."
            ),
            model_client=model_client,
            tools=[FunctionTool(x, description=x.__doc__) for x in [
                lights_plugin.get_state, lights_plugin.change_state]],
            delegate_tools=[transfer_back_to_triage_tool],
            agent_topic_type=lights_agent_topic_type,
            user_topic_type=user_topic_type,
        ),
    )
    # Add subscriptions for the lights agent: it will receive messages published to its own topic only.
    await runtime.add_subscription(TypeSubscription(topic_type=lights_agent_topic_type, agent_type=lights_agent_type.type))

    # Register the issues and repairs agent.
    meals_agent_type = await AIAgent.register(
        runtime,
        type=meals_agent_topic_type,  # Using the topic type as the agent type.
        factory=lambda: AIAgent(
            description="An meals agent.",
            system_message=SystemMessage(
                content="You are a an agent that can provide information about dishes for meals."
                "You can also use tools to add dishes to meals, remove dishes from meals and get the steps for preparing a meal."
                "Answer in a sentence or less except when showing meal steps. In that case show a list of steps in time order."
            ),
            model_client=model_client,
            tools=[FunctionTool(x, description=x.__doc__) for x in [meals_plugin.add_meal, meals_plugin.get_dish_options, meals_plugin.get_dishes,
                                                                    meals_plugin.get_meal_steps, meals_plugin.get_time_to_be_ready, meals_plugin.remove_dish, meals_plugin.set_time_to_be_ready]],
            delegate_tools=[transfer_back_to_triage_tool],
            agent_topic_type=meals_agent_topic_type,
            user_topic_type=user_topic_type,
        ),
    )
    # Add subscriptions for the issues and repairs agent: it will receive messages published to its own topic only.
    await runtime.add_subscription(
        TypeSubscription(topic_type=meals_agent_topic_type,
                         agent_type=meals_agent_type.type)
    )

    # Register the user agent.
    user_agent_type = await UserAgent.register(
        runtime,
        type=user_topic_type,
        factory=lambda: UserAgent(
            description="A user agent.",
            user_topic_type=user_topic_type,
            agent_topic_type=triage_agent_topic_type,
        ),
    )
    # Add subscriptions for the user agent: it will receive messages published to its own topic only.
    await runtime.add_subscription(TypeSubscription(topic_type=user_topic_type, agent_type=user_agent_type.type))

    # Start the runtime.
    runtime.start()

    # Create a new session for the user.
    session_id = str(uuid.uuid4())
    await runtime.publish_message(UserLogin(), topic_id=TopicId(user_topic_type, source=session_id))

    # Run until completion.
    await runtime.stop_when_idle()


asyncio.run(main())
