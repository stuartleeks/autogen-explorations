import asyncio
import json
import logging


from auto_gen_explore import config
from auto_gen_explore.app_web.session import AgentSession
from auto_gen_explore.plugins.utils import Console2


# https://en.wikipedia.org/wiki/ANSI_escape_code#8-bit
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


agent_session = AgentSession(id="test")

async def run_team_stream() -> None:
    user_message=input(f"{yellow}User (type 'exit' to close the session): {reset}")
    if user_message.strip().lower() == "exit":
        return
    task_result=await Console2(agent_session.run(user_message))
    last_message=task_result.messages[-1]

    # while isinstance(last_message, HandoffMessage) and last_message.target == "user": # use this normally (i.e. not using AgentTextMessageTermination)
    while True: # use this if using AgentTextMessageTermination
        state = await agent_session.save_state()
        # print()
        # print()
        # print(state)
        # print()
        with open(f".swarm_state.json", "w") as f:
            json.dump(state, f)

        user_message=input(f"{yellow}User (type 'exit' to close the session): {reset}")
        if user_message.strip().lower() == "exit":
            return

        task_result=await Console2(
            agent_session.run(user_message)
            # agent_session.run(user_input=HandoffMessage(
                # source="user", target=last_message.source, content=user_message))
        )
        # last_message=task_result.messages[-1]



# Use asyncio.run(...) if you are running this in a script.


asyncio.run(run_team_stream())
