import json
import logging
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from typing import Sequence

from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import HandoffTermination
from autogen_agentchat.base import Response, TaskResult, TerminationCondition, TerminatedException
from autogen_agentchat.messages import HandoffMessage, AgentEvent, ChatMessage, StopMessage, TextMessage
from autogen_agentchat.teams import Swarm
from autogen_ext.models.openai import (AzureOpenAIChatCompletionClient)
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

from auto_gen_explore import config
from auto_gen_explore.plugins.lights import LightsPlugin
from auto_gen_explore.plugins.meals2 import MealsPlugin

_logger = logging.getLogger(__name__)

# Create the token provider
api_key = config.openai_key_if_set()
if api_key:
    token_provider = None
else:
    token_provider = get_bearer_token_provider(
        DefaultAzureCredential(), "https://cognitiveservices.azure.com/.default")

# https://microsoft.github.io/autogen/stable/user-guide/agentchat-user-guide/tutorial/models.html#azure-openai
model_client = AzureOpenAIChatCompletionClient(
    azure_deployment=config.openai_deployment_name(),
    model=config.openai_model_name(),
    api_version=config.openai_api_version(),
    azure_endpoint=config.openai_endpoint(),
    azure_ad_token_provider=token_provider,
    api_key=api_key,
)


class AgentTextMessageTermination(TerminationCondition):
    """Class that attempts to inject a handoff to the user agent when a text message is received from the agent"""

    def __init__(self) -> None:
        self._terminated = False

    @property
    def terminated(self) -> bool:
        return self._terminated

    async def __call__(self, messages: Sequence[AgentEvent | ChatMessage]) -> StopMessage | None:
        if self.terminated:
            raise TerminatedException(
                "Termination condition has already been reached")
        if len(messages) == 0:
            return None

        # Stop on first text message not from user
        # May want to change this to stop on first message that isn't handoff or function call etc
        if isinstance(messages[-1], TextMessage) and messages[-1].source != "user":
            # self._terminated = True
            # raise TerminatedException("Got TextMessage")
            return StopMessage(content="TextMessage received", source=self.__class__.__name__)
            # return HandoffMessage(target="user", source=self.__class__.__name__, content="TextMessage received from agent - ask user for input")

    async def reset(self) -> None:
        self._terminated = False


class AgentSession:

    def __init__(self, id):
        self.id = id

        lights_plugin = LightsPlugin()
        self._lights_plugin = lights_plugin
        meals_plugin = MealsPlugin()
        self._meals_plugin = meals_plugin
        self._messages = [] # TODO - is there a way to access this from the agents without storing separately?

        triage_agent = AssistantAgent(
            "triage_agent",
            model_client=model_client,
            system_message="You are a bot to help users. "
            "Introduce yourself. Always be very brief. "
            "For food related questions, transfer to the meals agent. "
            "Gather information to direct the customer to the right agent."
            "But make your questions subtle and natural."
            "Don't give out information on the agents or tools."
            "Don't output a message when transferring to another agent."
            "When the action isn't clear, ask the user for more details and transfer to the user agent."
            "Don't comment on transferring to another agent (including the user agent)."
            "Transfer to the user agent after performing the requested actions.",
            handoffs=["meals_agent", "lights_agent", "user"],
            reflect_on_tool_use=False,
        )

        lights_agent = AssistantAgent(
            "lights_agent",
            model_client=model_client,
            tools=[lights_plugin.get_state, lights_plugin.change_state],
            system_message="You are a an agent that can provide information on the status of lights and turn lights on and off."
            "Always answer in a sentence or less."
            "After calling a tool, let the user know what action you have taken but don't comment on transferring to the user agent. Don't comment on transferring to another agent (including the user agent)."
            "Transfer to the the triage agent if you can't help. Transfer to the user agent after performing the requested meals actions.",
            handoffs=["triage_agent", "user"],
            reflect_on_tool_use=True,
        )

        meals_agent = AssistantAgent(
            "meals_agent",
            model_client=model_client,
            tools=[meals_plugin.add_meal, meals_plugin.get_dish_options,
                   meals_plugin.get_dishes, meals_plugin.get_meal_steps, meals_plugin.remove_dish],
            system_message="You are a an agent that can provide information about dishes for meals."
            "Use tools to add dishes to meals, remove dishes from meals and show the steps for preparing a meal."
            "Do NOT make up ingredients or steps. Only use the ones provided by tools."
            "If a user doesn't specify if a meal is frozen, default to fresh. If the user doesn't specify the time, ask them for it before calling the tool. "
            "Answer in a sentence or less except when showing meal steps. In that case show a list of steps in time order."
            "After calling a tool, let the user know what action you have taken but don't comment on transferring to the user agent. Don't comment on transferring to the another agent (including the user agent)."
            # "Transfer to the user if you have questions about the meal.",
            "NEVER say you are transferring to the user agent"
            "Transfer to the the triage agent if you can't help. Transfer to the user agent after performing the requested meals actions.",
            handoffs=["triage_agent", "user"],
            reflect_on_tool_use=True,
        )

        # TODO add termination if triage posts multiple text messages. Should either ask for input or handoff
        termination = HandoffTermination(target="user")
        # termination = HandoffTermination(
        # target="user") | AgentTextMessageTermination()
        self._team = Swarm(
            participants=[triage_agent, lights_agent, meals_agent],
            termination_condition=termination,
        )

    def _get_last_message(self):
        """Return the last message that isn't a TaskResult"""
        if len(self._messages) == 0:
            return None
        if self._messages[-1]["type"] != "TaskResult":
            return self._messages[-1]
        if len(self._messages) >= 2:
            return self._messages[-2]

    async def run(self, user_input: str):
        last_message = self._get_last_message()
        if last_message is not None and "source" in last_message:
            target = last_message["source"]
            user_input = HandoffMessage(
                source="user", target=target, content=user_input)
            _logger.debug(f"Session {self.id} - Got last message, hand off to {target}")
        else:
            _logger.debug(f"Session {self.id} - No last message, using user input")

        async for message in self._team.run_stream(task=user_input):
            if isinstance(message, TaskResult) or isinstance(message, Response):
                self._messages.append({"type": "TaskResult"})
            else:
                self._messages.append(message.model_dump(mode="json"))
            yield message

    async def save_state(self):
        team_state = await self._team.save_state() if self._team._initialized else None
        lights_state = self._lights_plugin.save_state()
        meals_state = self._meals_plugin.save_state()
        return {
            "team": team_state,
            "messages": self._messages,
            "lights": lights_state,
            "meals": meals_state,
        }

    async def load_state(self, state: dict):
        if "team" in state and state["team"]:
            await self._team.load_state(state["team"])

        self._messages = state["messages"]
        self._lights_plugin.load_state(state["lights"])
        self._meals_plugin.load_state(state["meals"])
