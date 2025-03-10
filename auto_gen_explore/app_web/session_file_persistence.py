import json
import os
from auto_gen_explore.app_web.session import AgentSession

_base_path = "./.app_web_state"


def _filename_for_session(session_id):
    file_name = os.path.join(_base_path, f"session_{session_id}.json")
    return file_name


async def save_session(session: AgentSession):
    if not os.path.exists(_base_path):
        os.makedirs(_base_path)
    file_name = _filename_for_session(session.id)
    with open(file_name, "w") as f:
        state = await session.save_state()
        f.write(json.dumps(state))


async def load_session(id) -> AgentSession:
    file_name = _filename_for_session(id)
    if not os.path.exists(file_name):
        return None
    with open(file_name, "r") as f:
        state = json.loads(f.read())
        session = AgentSession(id)
        await session.load_state(state)
        return session
