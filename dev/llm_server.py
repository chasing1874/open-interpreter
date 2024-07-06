# server.py

from json import dumps, loads
from typing import Any, Optional
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, StreamingResponse
import os
import platform
from pydantic import BaseModel
from interpreter.core.core import OpenInterpreter
from utils.prompts import PROMPTS
from uvicorn import Config, Server
import shutil

class RequestModel(BaseModel):
    prompt: str
    files: list[dict]
    system_prompt: str
    stop: Optional[list[str]]
    user: str
    model_name: str
    api_key: str
    conversation_id: str
    model_parameters: dict[str, Any]

class OI_server:
    def __init__(self):
        # self.interpreter = interpreter
        self.conversation_id = ''
        self.app = FastAPI()
        self.OI_session: dict[str, OpenInterpreter] = {}
        self.system = platform.system()

    def _OI_instance(self, requset: RequestModel) -> OpenInterpreter:
        print(f"requset.conversation_id: {requset.conversation_id}")
        if requset.conversation_id not in self.OI_session:
            new_OI = OpenInterpreter()

            # default parameters
            new_OI.llm.temperature = 0.0
            new_OI.auto_run = True
            new_OI.llm.context_window = 32000
            new_OI.llm.max_tokens=4000
            # interpreter.conversation_history=
            new_OI.llm.supports_vision=True
            new_OI.computer.emit_images=True
            new_OI.system_message = PROMPTS.system_message_win
            new_OI.llm.model = "gpt-4o"
            if self.system == 'Windows':
                new_OI.conversation_filename='D:\\code\\open-interpreter\\dev\\conversations\\test.json'
                new_OI.system_message = PROMPTS.system_message_win
            else:
                new_OI.system_message = PROMPTS.system_message_analyse

            # custom parameters
            new_OI.llm.model = requset.model_name
            new_OI.llm.api_key = requset.api_key
            new_OI.system_message += requset.system_prompt
            for key, value in requset.model_parameters.items():
                setattr(new_OI.llm, key, value)

            # save to session
            self.OI_session[requset.conversation_id] = new_OI
            self.conversation_id = requset.conversation_id
        return self.OI_session[requset.conversation_id]

    def run(self):

        app = self.app

        @app.post("/chat")
        def chat_endpoint(item: RequestModel):
            OI = self._OI_instance(item)
            
            result = OI.chat(item.prompt, stream=False, display=False)

            return JSONResponse(content=result)

        @app.post("/stream_chat")
        def stream_chat_endpoint(item: RequestModel):

            print('os system: ', self.system)

            if self.system == 'Windows':
                storage_path = 'D:\\code\\dify\\api\\storage\\'
                tmp_path = 'D:\\mnt\\data\\'
            elif self.system == 'Macos':
                storage_path = '/Users/jiangziyou/github/dify/api/storage/'
                tmp_path = '/Users/jiangziyou/mnt/data/'
            else:
                storage_path = '/root/code/dify/docker/volumes/app/storage/'
                tmp_path = '/mnt/data/'
           

            file_paths = ''
            file_cnt = len(item.files)
            for file in item.files:
                src_path = os.path.join(storage_path, file['file_path'].replace('/', '\\'))
                dest_path = os.path.join(tmp_path, file['sheet_name'].replace('/', '\\'))
                print('src: ', src_path)
                print('dest: ', dest_path)
                shutil.copyfile(src_path, dest_path)
                file_paths += f'{dest_path} \t'
            print(f"file_paths: {file_paths}")

            if file_cnt == 0:
                join_prompt = item.prompt
            else:
                join_prompt = f'我上传了{file_cnt}个文件，文件地址为: {file_paths}, 请按照下面的要求进行分析: \n{item.prompt}'
            print(join_prompt)

            OI = self._OI_instance(item)
            print(OI)
            print('OI.messages:', OI.messages)

            def event_stream():
                for chunk in OI.chat(join_prompt, display=False, stream=True):
                    print(f"chunk: {chunk}")
                    chunk_json = dumps(chunk)
                    print(f"chunk_json: {chunk_json}")
                    yield f"data: {chunk_json}\r\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")
        
        @app.get("/history")
        def history_endpoint(conversation_id: str):
            OI = self.OI_session[conversation_id]
            if OI is None:
                return []
            return OI.messages

        @app.get("/reset")
        def reset_endpoint(conversation_id: str):
            OI = self.OI_session[conversation_id]
            if OI is None:
                return []
            OI.reset()
            return OI.messages

        @app.get("/test")
        def test_endpoint(conversation_id: str):
            OI = self.OI_session[conversation_id]
            if OI is None:
                return 'OI not found'
            OI.chat()
        
        config = Config(app, host="0.0.0.0", port=8090) 
        server = Server(config)
        server.run()

server = OI_server()
server.run()
