# server.py

from json import dumps, loads
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, StreamingResponse
import interpreter
from pydantic import BaseModel
from utils.prompts import PROMPTS
from uvicorn import Config, Server

OI = interpreter.OpenInterpreter()

class LLMConfigModel(BaseModel):
    model: str
    temperature: float
    context_window: int
    max_tokens: int
    max_output: int
    api_key: str

class RequestModel(BaseModel):
    prompt: str
    llm_config: LLMConfigModel

app = FastAPI()
OI.auto_run = True
OI.llm.context_window = 32000
OI.llm.max_tokens=4000
# interpreter.conversation_filename=
# interpreter.conversation_history=
OI.llm.supports_vision=True
OI.computer.emit_images=True
OI.system_message = PROMPTS.system_message_analyse



@app.post("/chat")
def chat_endpoint(item: RequestModel):
    llm_config = item.llm_config
    if llm_config and "model" in llm_config:
        OI.llm.model = llm_config["model"]
    if llm_config and "api_key" in llm_config:
        OI.llm.api_key = llm_config["api_key"]

    OI.llm.model = "gpt-4o"
    result = OI.chat(item.prompt, stream=False, display=False)

    return JSONResponse(content=result)

@app.post("/stream_chat")
def stream_chat_endpoint(item: RequestModel):
    llm_config = item.llm_config
    print(llm_config)
    if llm_config and "model" in llm_config:
        OI.llm.model = llm_config["model"]
    if llm_config and "api_key" in llm_config:
        OI.llm.api_key = llm_config["api_key"]


    def event_stream():
        for chunk in OI.chat(item.prompt, display=False, stream=True):
            print(f"chunk: {chunk}")
            chunk_json = dumps(chunk)
            print(f"chunk_json: {chunk_json}")
            yield f"data: {chunk_json}\r\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/history")
def history_endpoint():
    return OI.messages

@app.get("/reset")
def reset_endpoint():
    OI.reset()
    return OI.messages

@app.get("/test")
def test_endpoint():
    OI.chat()

config = Config(app, host="0.0.0.0", port=8090) 
server = Server(config)
server.run()
