from pydantic_settings import SettingsConfigDict, BaseSettings

class ShulingConfig(BaseSettings):

    OPENAI_API_KEY: str
    OPENROUTER_API_KEY: str
    ZHIPU_API_KEY: str
    ZHIPU_API_BASE: str

    STORAGE_TYPE: str
    STORAGE_LOCAL_PATH: str

    # Aliyun oss Storage configuration
    ALIYUN_OSS_BUCKET_NAME: str
    ALIYUN_OSS_ACCESS_KEY: str
    ALIYUN_OSS_SECRET_KEY: str
    ALIYUN_OSS_ENDPOINT: str
    ALIYUN_OSS_AUTH_VERSION:str
    ALIYUN_OSS_REGION: str


    model_config = SettingsConfigDict(
        # read from dotenv format config file
        env_file='.env',
        env_file_encoding='utf-8',
        frozen=True,

        # ignore extra attributes
        extra='ignore',
    )
