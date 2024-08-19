from json import load
import mimetypes
import os
import platform
from typing import Any, Dict, Optional, Union
import time
from urllib.parse import urlparse
from dev.services.file_service import FileService
import shortuuid
import requests
from pydantic import BaseModel
from cacheout import LRUCache
from fastapi import FastAPI
from interpreter.core.core import OpenInterpreter
from interpreter.terminal_interface.utils.local_storage_path import get_storage_path
from dev.utils.prompts import PROMPTS


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
    prompt: Union[str, list[Dict]]
    files: list[dict]
    system_prompt: str
    stop: Optional[list[str]]
    user: str
    model_name: str
    api_key: str
    conversation_id: str
    model_parameters: dict[str, Any]

class ShulingApp(FastAPI):
    config: dict[str, Any]

    def __init__(self):

        super().__init__(title="Shuling", description="Shuling API", version="0.0.1")

        def reset_OI(key, value, cause):
            print(f"reset_OI: key: {key}, value: {value}, cause: {cause}")
            value.reset()

        self.system = platform.system()
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
                new_OI.conversation_history_path = 'D:\\code\\open-interpreter\\dev\\conversations'
                new_OI.conversation_filename = user_id + '.json'
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
            new_OI.conversation_history=True
            new_OI.llm.supports_vision=True
            new_OI.computer.emit_images=True
            new_OI.disable_telemetry = True
            new_OI.contribute_conversation = False
            new_OI.llm.model = "gpt-4o"
            if self.system == 'Windows':
                new_OI.conversation_history_path = 'D:\\code\\open-interpreter\\dev\\conversations'
                new_OI.conversation_filename = requset.conversation_id + '.json'
                new_OI.system_message = PROMPTS.system_message_win
            else:
                new_OI.conversation_filename = requset.conversation_id + '.json'
                new_OI.system_message = PROMPTS.system_message_analyse

            # custom parameters
            new_OI.llm.model = requset.model_name
            new_OI.llm.api_key = requset.api_key
            for key, value in requset.model_parameters.items():
                print(f"model_parameters: key: {key}, value: {value}")
                setattr(new_OI.llm, key, value)
            
            cur_conversation_path = os.path.join(get_storage_path("conversations"), requset.conversation_id + '.json')
            print(f'cur_conversation_path: {cur_conversation_path}')
            if os.path.exists(cur_conversation_path):
                print(f'exsits path')
                with open(cur_conversation_path, "r") as f:
                    messages = load(f)
                    new_OI.messages = messages

            # save to session
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
        elif self.system == 'Darwin':
            storage_path = '/Users/jiangziyou/github/dify/api/storage/'
            return os.path.join(storage_path, file['file_path'])
        else:
            storage_path = '/root/code/dify/docker/volumes/app/storage/'
            return os.path.join(storage_path, file['file_path'])
    
    def _get_dest_path(self, file: dict):
        if self.system == 'Windows':
            tmp_path = 'D:\\mnt\\data\\'
            return os.path.join(tmp_path, file['sheet_name'].replace('/', '\\'))
        elif self.system == 'Darwin':
            tmp_path = '/Users/jiangziyou/mnt/data/'
            return os.path.join(tmp_path, file['sheet_name'])
        else:
            tmp_path = '/mnt/data/'
            return os.path.join(tmp_path, file['sheet_name'])
    

    def _get_mnt_file_path(self, user_id, file_name, file_extension):
        if not os.path.splitext(file_name)[1]:
            file_name = file_name + '.' + file_extension
        if self.system == 'Windows':
            # base_dir = os.path.join(f"D:\\workspace\\{user_id}", "mnt", "data")
            base_dir = os.path.join(f"D:\\workspace\\{user_id}", "workspace")
        elif self.system == 'Darwin':
            base_dir = os.path.join(f"/Users/jiangziyou/workspace/{user_id}", "workspace")
        else:
            base_dir = os.path.join(f"/workspace/{user_id}", "workspace")
        os.makedirs(base_dir, exist_ok=True)
        return os.path.join(base_dir, file_name)
        
    
    def _download_file_from_url(self, user_id, upload_file_url, upload_file_name=None):
        def get_file_extension_from_url(url: str):
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

        if not upload_file_url.startswith('http'):
            upload_file_url = 'http://localhost' + upload_file_url

        if upload_file_name is None:
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
        elif self.system == 'Darwin':
            base_dir = '/Users/jiangziyou/workspace/'
        else:
            base_dir = '/workspace/'
        cur_work_path = os.path.join(base_dir, user_id)
        os.makedirs(cur_work_path, exist_ok=True)
        chdir_code = f'import os\nos.chdir("{cur_work_path}")\nprint(os.getcwd())'
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
        
    def _compare_file_info(self, before, after, user_id):
        """Compare two file info dictionaries and return a list of new or modified files."""
        pic_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff'}
        piclist = []
        filelist = []

        for file in after:
            if file not in before or after[file] != before[file]:
                file_url = FileService.upload_file(file, user_id)
                if os.path.splitext(file)[1].lower() in pic_extensions:
                    print(f'piclist: {file}')
                    piclist.append(file_url)
                else:
                    print(f'filelist: {file}')
                    filelist.append(file_url)
        
        return piclist, filelist