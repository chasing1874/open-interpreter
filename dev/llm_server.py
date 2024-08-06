# server.py

from json import dumps, loads
import time
from typing import Any, Dict, Optional
import logging
import requests
import mimetypes
from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, StreamingResponse
import os
import platform
from pydantic import BaseModel
import shortuuid
from interpreter.core.core import OpenInterpreter
from utils.prompts import PROMPTS
from uvicorn import Config, Server
import shutil
from cacheout import LRUCache

logger = logging.getLogger(__name__)

class ExcutionResult(BaseModel):
    execution_state: str
    final_output: list
    error_msg: Optional[str]
    pic_list: list[str]
    file_list: list[str]

class ExcutionResponse(BaseModel):
    code: int
    msg: str
    result: Optional[ExcutionResult]



class RequestModel(BaseModel):
    prompt: str | list[dict]
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

        def reset_OI(key, value, cause):
            print(f"reset_OI: key: {key}, value: {value}, cause: {cause}")
            value.reset()

        self.conversation_id = ''
        self.system = platform.system()
        self.app = FastAPI()
        self.OI_session: LRUCache[str, OpenInterpreter] = LRUCache(maxsize=20, ttl=600, timer=time.time)
        self.OI_session_4_user: LRUCache[str, OpenInterpreter] = LRUCache(maxsize=20, ttl=600, timer=time.time)
        
        self.OI_session.on_delete = reset_OI
        self.OI_session.on_get = lambda key, value, exsits: self.OI_session.set(key, value) if exsits else None

        self.OI_session_4_user.on_delete = reset_OI
        self.OI_session_4_user.on_get = lambda key, value, exsits: self.OI_session_4_user.set(key, value) if exsits else None


    def _OI_instance_4_user(self, payload: Dict[str, Any]) -> OpenInterpreter:
        conversation_id = payload.get("conversation_id")
        user_id = payload.get("user_id")
        if conversation_id and self.OI_session.has(conversation_id):
            return self.OI_session.get(conversation_id)
        if not user_id or user_id == '':
            user_id = shortuuid.uuid()

        if not self.OI_session_4_user.has(user_id):
            new_OI = OpenInterpreter()

            # default parameters
            new_OI.llm.temperature = 0.0
            new_OI.auto_run = True
            new_OI.llm.context_window = 32000
            new_OI.llm.max_tokens=4000
            # interpreter.conversation_history=
            new_OI.llm.supports_vision=True
            new_OI.computer.emit_images=True
            new_OI.disable_telemetry = True
            new_OI.llm.model = "gpt-4o"
            if self.system == 'Windows':
                new_OI.conversation_filename='D:\\code\\open-interpreter\\dev\\conversations\\test.json'
                new_OI.system_message = PROMPTS.system_message_win
            else:
                new_OI.system_message = PROMPTS.system_message_analyse
            # save to session
            self.OI_session_4_user.set(user_id, new_OI)
        return self.OI_session_4_user.get(user_id)

    def _OI_instance(self, requset: RequestModel) -> OpenInterpreter:
        print(f"requset.conversation_id: {requset.conversation_id}")
        if not requset.conversation_id or requset.conversation_id == '':
            requset.conversation_id = shortuuid.uuid()
        # if requset.conversation_id not in self.OI_session:
        if not self.OI_session.has(requset.conversation_id):
            new_OI = OpenInterpreter()

            # default parameters
            new_OI.llm.temperature = 0.0
            new_OI.auto_run = True
            new_OI.llm.context_window = 32000
            new_OI.llm.max_tokens=4000
            # interpreter.conversation_history=
            new_OI.llm.supports_vision=True
            new_OI.computer.emit_images=True
            new_OI.disable_telemetry = True
            new_OI.llm.model = "gpt-4o"
            if self.system == 'Windows':
                new_OI.conversation_filename='D:\\code\\open-interpreter\\dev\\conversations\\test.json'
                new_OI.system_message = PROMPTS.system_message_win
            else:
                new_OI.system_message = PROMPTS.system_message_analyse

            # custom parameters
            new_OI.llm.model = requset.model_name
            new_OI.llm.api_key = requset.api_key
            for key, value in requset.model_parameters.items():
                print(f"model_parameters: key: {key}, value: {value}")
                setattr(new_OI.llm, key, value)

            # save to session
            # self.OI_session[requset.conversation_id] = new_OI
            self.OI_session.set(requset.conversation_id, new_OI)
            self.conversation_id = requset.conversation_id
        return self.OI_session.get(requset.conversation_id)
    
    def _get_default_system_message(self):
        if self.system == 'Windows':
            return PROMPTS.system_message_win
        return PROMPTS.system_message_analyse
    
    def _get_src_path(self, file: dict):
        if self.system == 'Windows':
            storage_path = 'D:\\code\\dify\\api\\storage\\'
            return os.path.join(storage_path, file['file_path'].replace('/', '\\'))
        elif self.system == 'Macos':
            storage_path = '/Users/jiangziyou/github/dify/api/storage/'
            return os.path.join(storage_path, file['file_path'])
        else:
            storage_path = '/root/code/dify/docker/volumes/app/storage/'
            return os.path.join(storage_path, file['file_path'])
    
    def _get_dest_path(self, file: dict):
        if self.system == 'Windows':
            tmp_path = 'D:\\mnt\\data\\'
            return os.path.join(tmp_path, file['sheet_name'].replace('/', '\\'))
        elif self.system == 'Macos':
            tmp_path = '/Users/jiangziyou/mnt/data/'
            return os.path.join(tmp_path, file['sheet_name'])
        else:
            tmp_path = '/mnt/data/'
            return os.path.join(tmp_path, file['sheet_name'])
    

    def _get_mnt_file_path(self, user_id, file_name, file_extension):
        if not os.path.splitext(file_name)[1]:
            file_name = file_name + '.' + file_extension
        if self.system == 'Windows':
            base_dir = os.path.join(f"D:\\workspace\\{user_id}", "mnt", "data")
        elif self.system == 'Macos':
            base_dir = os.path.join(f"/Users/jiangziyou/workspace/{user_id}", "mnt", "data")
        else:
            base_dir = os.path.join(f"/workspace/{user_id}", "mnt", "data")
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, file_name)
        
    
    def _download_file_from_url(self, user_id, upload_file_url, upload_file_name=None):
        def get_file_extension_from_url(url):
            response = requests.head(url)
            print(f"response.headers: {response.headers}")
            if 'Content-Disposition' in response.headers:
                content_disposition = response.headers['Content-Disposition']
                if 'filename=' in content_disposition:
                    filename = content_disposition.rsplit('filename=')[1].split(';')[0].strip('"')
                    return filename.split('.')[-1]
            if 'Content-Type' in response.headers:
                mimetype = response.headers['Content-Type']
                extension = mimetypes.guess_extension(mimetype)
                if extension:
                    return extension.lstrip('.')
            parsed_url = urlparse(url)
            return parsed_url.path.split('.')[-1]

        if upload_file_name is None:
            from urllib.parse import urlparse
            parsed_url = urlparse(upload_file_url)
            upload_file_name = parsed_url.path.split('/')[-1]

        file_extension = get_file_extension_from_url(upload_file_url)
        print(f"file_extension: {file_extension}")

        mnt_file_path = self._get_mnt_file_path(user_id, upload_file_name, file_extension)
        print(f"mnt_file_path: {mnt_file_path}")

        response = requests.get(upload_file_url, stream=True)
        
        if response.status_code == 200:
            with open(mnt_file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
        else:
            raise Exception(f"Failed to download file. Status code: {response.status_code}")
        
    def _change_workspace_dir(self, user_id, OI: OpenInterpreter):
        base_dir = ''
        if self.system == 'Windows':
            base_dir = 'D:/workspace/'
        elif self.system == 'Macos':
            base_dir = '/Users/jiangziyou/workspace/'
        else:
            base_dir = '/workspace/'
        cur_work_path = os.path.join(base_dir, user_id)
        os.makedirs(cur_work_path, exist_ok=True)
        chdir_code = f'import os\nos.chdir("{cur_work_path}")'
        out = OI.computer.run("python", chdir_code)
        print(f'out: {out}')
        return cur_work_path
    
    def _get_file_info(self, directory):
        """Returns a dictionary with filenames and their modification times."""
        file_info = {}
        for root, dirs, files in os.walk(directory):
            for file in files:
                filepath = os.path.join(root, file)
                normalized_path = os.path.normpath(filepath)
                file_info[normalized_path] = os.path.getmtime(normalized_path)
        return file_info
        
    def _compare_file_info(self, before, after):
        """Compare two file info dictionaries and return a list of new or modified files."""
        pic_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
        piclist = []
        filelist = []

        for file in after:
            if file not in before or after[file] != before[file]:
                if os.path.splitext(file)[1].lower() in pic_extensions:
                    piclist.append(file)
                else:
                    filelist.append(file)
        
        return piclist, filelist
        


    def run(self):

        app = self.app

        @app.post("/chat")
        async def chat_endpoint(item: RequestModel):
            OI = self._OI_instance(item)
            
            result = OI.chat(item.prompt, stream=False, display=False)

            return JSONResponse(content=result)

        @app.post("/stream_chat")
        async def stream_chat_endpoint(item: RequestModel):
            print(f"item.prompt: {item.prompt}")

            file_paths = ''
            file_cnt = len(item.files)
            for file in item.files:
                src_path = self._get_src_path(file)
                dest_path = self._get_dest_path(file)
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
            if item.system_prompt:
                OI.system_message = self._get_default_system_message() + item.system_prompt
                print(f'cur system_message: ----------------------------↓↓↓------------------------ \n  {OI.system_message}')

            def event_stream():
                for chunk in OI.chat(join_prompt, display=False, stream=True):
                    chunk_json = dumps(chunk)
                    print(f'chunk: {chunk}')
                    # print(f'chunk_json: {chunk_json}')
                    yield f"data: {chunk_json}\r\n"

            return StreamingResponse(event_stream(), media_type="text/event-stream")
        
        @app.get("/history")
        async def history_endpoint(conversation_id: str):
            OI = self.OI_session.get(conversation_id)
            if OI is None:
                return []
            return OI.messages

        @app.get("/reset")
        async def reset_endpoint(conversation_id: str):
            OI = self.OI_session.get(conversation_id)
            if OI is None:
                return []
            OI.reset()
            return OI.messages

        @app.get("/test")
        async def test_endpoint(conversation_id: str):
            OI = self.OI_session.get(conversation_id)
            if OI is None:
                return 'OI not found'
            OI.chat()

        @app.post("/run")
        async def run_code(payload: Dict[str, Any]):
            user_id = payload.get("user_id")
            OI = self._OI_instance_4_user(payload)
            language, code, upload_file_name, upload_file_url = payload.get("language"), payload.get("code"), payload.get("upload_file_name"), payload.get("upload_file_url")
            if not (language and code):
                return {"error": "Both 'language' and 'code' are required."}, 400
            try:
                cur_work_dir = self._change_workspace_dir(user_id, OI)
                
                if upload_file_url:
                    self._download_file_from_url(user_id, upload_file_url, upload_file_name)
                    print(f"upload_file_url: {upload_file_url}")

                # Get initial state of the directory
                initial_file_info = self._get_file_info(cur_work_dir)

                # Run the code
                print(f"Running {language}:", code)
                output = OI.computer.run(language, code)
                print("Output:", output)

                # Get final state of the directory
                final_file_info = self._get_file_info(cur_work_dir)
                # Compare file info to get new or modified files
                piclist, filelist = self._compare_file_info(initial_file_info, final_file_info)

                return {
                    'code': 200,
                    'msg': 'success',
                    'result': {
                        'execution_state': 'success',
                        'final_output': output,
                        'piclist': piclist,
                        'filelist': filelist
                    }
                }
            except Exception as e:
                return {'code': 200, 'msg': str(e)}
        
        @app.post("/test_run")
        async def test_run_code(requset: RequestModel):
            user_id = requset.user
            OI = self._OI_instance(requset)
            if len(user_id) == 5:
                chdir_code = f'import os\nos.chdir("D:/workspace/{user_id}")'
                out = OI.computer.run("python", chdir_code)
                print(out)
            code = f"import os\nprint(os.getcwd())\nprint(os.listdir())\n"
            output = OI.computer.run("python", code)
            return {"output": output}
        
        config = Config(app, host="0.0.0.0", port=8090) 
        server = Server(config)
        server.run()

server = OI_server()
server.run()