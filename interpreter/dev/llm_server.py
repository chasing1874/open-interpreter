# server.py

from json import dumps, loads
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, StreamingResponse
from interpreter import interpreter
from pydantic import BaseModel
from utils.prompts import PROMPTS


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
interpreter.auto_run = True
interpreter.llm.context_window = 8192
interpreter.llm.max_tokens=1000
# interpreter.conversation_filename=
# interpreter.conversation_history=
interpreter.llm.supports_vision=True
interpreter.computer.emit_images=True
interpreter.system_message = PROMPTS.system_message



@app.post("/chat")
def chat_endpoint(item: RequestModel):
    llm_config = item.llm_config
    if llm_config and "model" in llm_config:
        interpreter.llm.model = llm_config["model"]
    if llm_config and "api_key" in llm_config:
        interpreter.llm.api_key = llm_config["api_key"]

    result = interpreter.chat(item.prompt, stream=False, display=False)

    return JSONResponse(content=result)

@app.post("/stream_chat")
def stream_chat_endpoint(item: RequestModel):
    llm_config = item.llm_config
    print(llm_config)
    if llm_config and "model" in llm_config:
        interpreter.llm.model = llm_config["model"]
    if llm_config and "api_key" in llm_config:
        interpreter.llm.api_key = llm_config["api_key"]


    def event_stream():
        for chunk in interpreter.chat(item.prompt, display=False, stream=True):
            print(f"chunk: {chunk}")
            chunk_json = dumps(chunk)
            print(f"chunk_json: {chunk_json}")
            yield f"data: {chunk_json}\r\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")

@app.get("/history")
def history_endpoint():
    return interpreter.messages

@app.get("/reset")
def reset_endpoint():
    interpreter.reset()
    return interpreter.messages

@app.get("/test")
def test_endpoint():
    interpreter.chat()