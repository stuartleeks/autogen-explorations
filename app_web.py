import logging
from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from autogen_agentchat.base import Response, TaskResult
from nanoid import generate

from auto_gen_explore import config
from auto_gen_explore.app_web.session import AgentSession


logging.basicConfig(
    format="[%(asctime)s - %(name)s:%(lineno)d - %(levelname)s] %(message)s",
    # format=f"{grey}%(message)s{reset}",
    datefmt="%Y-%m-%d %H:%M:%S",
    # level=logging.DEBUG
)

# logging.getLogger("httpx").setLevel(logging.INFO) # useful to see the URLs used (e.g. when debugging a 404 for AOAI)
logging.getLogger("kernel").setLevel(config.semantic_kernel_log_level())

app = FastAPI()

sessions : dict[str, AgentSession] = {}

app.mount("/css", StaticFiles(directory="app_web/css"), name="css")
app.mount("/js", StaticFiles(directory="app_web/js"), name="js")

@app.get("/")
async def read_index():
    return FileResponse('app_web/index.html')


@app.post("/api/sessions")
async def create_session():
    session_id = generate(size=10)
    session = AgentSession(session_id)
    sessions[session.id] = session
    return {"id": session.id}

@app.websocket("/api/sessions/{id}")
async def websocket_endpoint(websocket: WebSocket, id: str):
    session = sessions.get(id)
    if session is None:
        raise ValueError(f"Session not found: {id}")

    await websocket.accept()
    # TODO on new connection send the message history
    while True:
        print("waiting for user input...")
        user_input = await websocket.receive_json()
        print("Got user input:", user_input)
        async for message in session.run(user_input["content"]):
            if isinstance(message, TaskResult) or isinstance(message, Response):
                # current run completed - break iterator to wait for next user input
                await websocket.send_json({"type": "TaskResult"})
                break
            await websocket.send_json(message.model_dump(mode="json"))




if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_web:app", host="0.0.0.0", port=3000, reload=True)