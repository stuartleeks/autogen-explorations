import asyncio
import logging
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from autogen_agentchat.base import Response, TaskResult
from nanoid import generate

from auto_gen_explore import config
from auto_gen_explore.app_web.session import AgentSession
# from auto_gen_explore.app_web.session_memory_persistence import load_session, save_session
from auto_gen_explore.app_web.session_file_persistence import load_session, save_session


logging.basicConfig(
    format="[%(asctime)s - %(name)s:%(lineno)d - %(levelname)s] %(message)s",
    # format=f"{grey}%(message)s{reset}",
    datefmt="%Y-%m-%d %H:%M:%S",
    # level=logging.DEBUG
)

# logging.getLogger("httpx").setLevel(logging.INFO) # useful to see the URLs used (e.g. when debugging a 404 for AOAI)
logging.getLogger("kernel").setLevel(config.semantic_kernel_log_level())

app = FastAPI()

state_folder = os.path.join(os.path.dirname(__file__), "./.app_web_state")

session_socket_managers: dict[str, "SessionWebSocketManager"] = {}


class SessionWebSocketManager:
    def __init__(self, session_id: str):
        self._websockets_lock = asyncio.Lock() # aquire this lock before accessing _websockets
        self._websockets_added = asyncio.Event() # signal when a websocket is added
        self._websockets = []
        self._session_id = session_id
        self._runner = None

    async def add_websocket(self, websocket):
        async with self._websockets_lock:
            # Send the message history
            session = await load_session(self._session_id)
            for message in session._messages:  # TODO this should be a method/property on AgentSession
                await websocket.send_json(message)

            # Add the websocket to the list of websockets
            self._websockets.append(websocket)
            self._websockets_added.set() # signal that a websocket was added

    async def _broadcast_json(self, payload):
        async with self._websockets_lock:
            if len(self._websockets) == 0:
                return

            send_tasks = [asyncio.create_task(self._safe_send_json(ws, payload))
                for ws in self._websockets]
    
        await asyncio.wait(
            send_tasks,
            return_when=asyncio.ALL_COMPLETED,
        )

    async def _safe_send_json(self, ws, payload):
        try:
            await ws.send_json(payload)
        except WebSocketDisconnect as wdse:
            print(f"WebSocketDisconnect (send): {wdse}")
            self._websockets.remove(ws)

    async def _receive_json(self):
        async with self._websockets_lock:
            if len(self._websockets) == 0:
                return None

            receive_tasks = [asyncio.create_task(self._safe_receive_json(ws))
                for ws in self._websockets]
            
            # Add a wait for the event that a websocket was added
            # This causes the receive tasks to be cancelled if a new websocket is added
            # The caller can then retry the receive with the newly added socket
            self._websockets_added.clear()
            socket_added_task = asyncio.create_task(self._websockets_added.wait())
            receive_tasks.append(socket_added_task)
        
        done, pending = await asyncio.wait(
            receive_tasks,
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
        
        completed = done.pop()
        if completed == socket_added_task:
            print("Socket added - retrying receive")
            return None
        
        return completed.result()

    async def _safe_receive_json(self, ws):
        try:
            return await ws.receive_json()
        except WebSocketDisconnect as wdse:
            print(f"WebSocketDisconnect (receive): {wdse}")
            self._websockets.remove(ws)

    def run(self):
        if self._runner is None:
            self._runner = asyncio.create_task(self._run())
        return self._runner

    async def _run(self):
        while True:
            print("waiting for user input...")
            user_input = await self._receive_json()
            if user_input is None:
                if len(self._websockets) == 0:
                    print("No user input - exiting run loop")
                    break
                print("No user input - retrying")
                continue
            
            print("Got user input:", user_input)
            session = await load_session(self._session_id)
            async for message in session.run(user_input["content"]):
                if isinstance(message, TaskResult) or isinstance(message, Response):
                    # current run completed - break iterator to wait for next user input
                    await self._broadcast_json({"type": "TaskResult"})
                else:
                    await self._broadcast_json(message.model_dump(mode="json"))
            await save_session(session)


app.mount("/css", StaticFiles(directory="app_web/css"), name="css")
app.mount("/js", StaticFiles(directory="app_web/js"), name="js")


@app.get("/")
async def read_index():
    return FileResponse('app_web/index.html')


@app.post("/api/sessions")
async def create_session():
    session_id = generate(size=10)
    session = AgentSession(session_id)
    await save_session(session)
    return {"id": session.id}


@app.websocket("/api/sessions/{id}")
async def websocket_endpoint(websocket: WebSocket, id: str):
    session = await load_session(id)
    if session is None:
        raise ValueError(f"Session not found: {id}")

    socket_manager = session_socket_managers.get(id)
    if socket_manager is None:
        socket_manager = SessionWebSocketManager(id)
        session_socket_managers[id] = socket_manager

    await websocket.accept()

    await socket_manager.add_websocket(websocket)
    await socket_manager.run()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_web:app", host="0.0.0.0", port=3000, reload=True)
