import uuid
from extensions.ext_storage import storage
from configs import shuling_config

class FileService:

    # https://BucketName.Endpoint/ObjectName

    @staticmethod
    def upload_file(file_path, uniq_id):
        extension = file_path.split('.')[-1]
        file_uuid = str(uuid.uuid4())
        file_key = 'upload_files/' + uniq_id + '/' + file_uuid + '.' + extension
        with open(file_path, 'rb') as f:
            file_content = f.read()

        storage.save(file_key, file_content)

        bucket = shuling_config.ALIYUN_OSS_BUCKET_NAME
        endpoint = shuling_config.ALIYUN_OSS_ENDPOINT

        return 'https://' + bucket + '.' + endpoint + '/' + file_key