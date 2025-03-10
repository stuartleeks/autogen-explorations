from auto_gen_explore.app_web.session import AgentSession


sessions: dict[str, AgentSession] = {}


async def save_session(session):
    sessions[session.id] = session


async def load_session(id):
    return sessions.get(id)
