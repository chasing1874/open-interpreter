# server.py

from json import dumps
from logging.handlers import RotatingFileHandler
import sys
from typing import Any, Dict
import logging
from fastapi.responses import JSONResponse, StreamingResponse
import os
from dev.extensions import ext_storage
from dev.shuling_app import RequestModel, ShulingApp
import shutil
from dev.configs import shuling_config

logger = logging.getLogger(__name__)


# ----------------------------
# Application Factory Function
# ----------------------------

def create_fastapi_app_with_config() -> ShulingApp:
    """
    create a raw fastApi app
    with configs loaded from .env file
    """
    sl_app = ShulingApp()
    sl_app.config = shuling_config.model_dump()
    print(f'config: {sl_app.config}')

    # populate configs into system environment variables
    for key, value in sl_app.config.items():
        if isinstance(value, str):
            os.environ[key] = value
        elif isinstance(value, int | float | bool):
            os.environ[key] = str(value)
        elif value is None:
            os.environ[key] = ''

    return sl_app

def create_app() -> ShulingApp:
    app = create_fastapi_app_with_config()

    log_handlers = None
    log_file = app.config.get("LOG_FILE")
    if log_file:
        log_dir = os.path.dirname(log_file)
        os.makedirs(log_dir, exist_ok=True)
        log_handlers = [
            RotatingFileHandler(
                filename=log_file,
                maxBytes=1024 * 1024 * 1024,
                backupCount=5,
            ),
            logging.StreamHandler(sys.stdout),
        ]

    logging.basicConfig(
        level=app.config.get("LOG_LEVEL"),
        format=app.config.get("LOG_FORMAT"),
        datefmt=app.config.get("LOG_DATEFORMAT"),
        handlers=log_handlers,
        force=True,
    )
    log_tz = app.config.get("LOG_TZ")
    if log_tz:
        from datetime import datetime

        import pytz

        timezone = pytz.timezone(log_tz)

        def time_converter(seconds):
            return datetime.utcfromtimestamp(seconds).astimezone(timezone).timetuple()

        for handler in logging.root.handlers:
            handler.formatter.converter = time_converter
    initialize_extensions(app)

    return app

def initialize_extensions(app: ShulingApp):
    # Since the application instance is now created, pass it to each FastaAi
    # extension instance to bind it to the Flask application instance (app)
    ext_storage.init_app(app.config)


# create app
app = create_app()

@app.post("/chat")
async def chat_endpoint(item: RequestModel):
    OI = app._OI_instance(item)
    
    result = OI.chat(item.prompt, stream=False, display=False)

    return JSONResponse(content=result)

@app.post("/stream_chat")
async def stream_chat_endpoint(item: RequestModel):
    print(f"item.prompt: {item.prompt}")

    file_paths = ''
    file_cnt = len(item.files)
    for file in item.files:
        src_path = app._get_src_path(file)
        dest_path = app._get_dest_path(file)
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

    OI = app._OI_instance(item)
    if item.system_prompt:
        OI.system_message = app._get_default_system_message() + item.system_prompt
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
    OI = app.OI_session.get(conversation_id)
    if OI is None:
        return []
    return OI.messages

@app.get("/reset")
async def reset_endpoint(conversation_id: str):
    OI = app.OI_session.get(conversation_id)
    if OI is None:
        return []
    OI.reset()
    return OI.messages

@app.post("/run")
async def run_code(payload: Dict[str, Any]):
    user_id = payload.get("user_id")
    OI = app._OI_instance_4_user(payload)
    language, code, upload_files = payload.get("language"), payload.get("code"), payload.get("upload_files")
    print(f'user_id: {user_id}, payload: {payload}')
    if not (language and code):
        return {"error": "Both 'language' and 'code' are required."}, 400
    try:
        cur_work_dir = app._change_workspace_dir(user_id, OI)
        
        if upload_files and len(upload_files) > 0:
            for upload_file in upload_files:
                upload_file_url = upload_file.get('url')
                upload_file_name = upload_file.get('filename')
                print(f"upload_file_url: {upload_file_url}, upload_file_name: {upload_file_name}")
                app._download_file_from_url(user_id, upload_file_url, upload_file_name)

        # Get initial state of the directory
        initial_file_info = app._get_file_info(cur_work_dir)

        # Run the code
        print(f"Running {language}:", code)
        print(f'OI: {OI}')
        final_code = str(code)
        output = OI.computer.run(language, code=final_code)
        print("Output:", output)

        # Get final state of the directory
        final_file_info = app._get_file_info(cur_work_dir)
        # Compare file info to get new or modified files
        piclist, filelist = app._compare_file_info(initial_file_info, final_file_info, user_id)

        res = {
            'code': 200,
            'msg': 'success',
            'result': {
                'execution_state': 'success',
                'final_output': output,
                'pic_list': piclist,
                'file_list': filelist
            }
        }

        print(f'res: {res}')

        return res
    except Exception as e:
        return {'code': 500, 'msg': str(e)}

@app.post("/test_run")
async def test_run_code(requset: RequestModel):
    user_id = requset.user
    OI = app._OI_instance(requset)
    if len(user_id) == 5:
        chdir_code = f'import os\nos.chdir("D:/workspace/{user_id}")'
        out = OI.computer.run("python", chdir_code)
        print(out)
    code = f"import os\nprint(os.getcwd())\nprint(os.listdir())\n"
    output = OI.computer.run("python", code)
    return {"output": output}
