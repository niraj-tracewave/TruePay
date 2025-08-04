import os
from functools import lru_cache

from pydantic import BaseModel
from pydantic_settings import BaseSettings


class ServerType(BaseModel):
    PRODUCTION: str = "production"
    DEVELOPMENT: str = "development"
    LOCAL: str = "local"


class Setting(BaseSettings):
    DATABASE_URL: str
    ALEMBIC_DATABASE_URL: str
    HOST_URL: str
    HOST_PORT: int
    ENV_FASTAPI_SERVER_TYPE: str
    JWT_SECRET_KEY: str
    JWT_REFRESH_SECRET_KEY: str
    AWS_ACCESS_KEY: str
    AWS_SECRET_KEY: str
    AWS_REGION: str
    AWS_BUCKET_NAME: str
    S3_BUCKET_URL: str
    SURPASS_API_BASE_URL: str
    SURPASS_TOKEN: str
    WHITELIST_MOBILE_NUMBER: str
    SMTP_USER_EMAIL: str
    SMTP_PASSWORD: str
    IS_PROD: str
    RECIPIENT_ADMIN_EMAIL: str
    RAZORPAY_KEY_ID: str
    RAZORPAY_SECRET: str
    GST_CHARGE: str

    # Default Log type
    LOG_LEVEL: str

    class Config:
        env_nested_delimiter = '__'
        env_file = ".env"  # set the env file path
        env_file_encoding = "utf-8"


app_settings = Setting()
_app_server_type = ServerType()


@lru_cache
def get_current_server_config():
    """
    This will check the FASTAPI_ENV variable and create an object of configuration according to that.
    :return: Production or Development Config object.
    """
    server_type = os.getenv("ENV_FASTAPI_SERVER_TYPE", _app_server_type.LOCAL)
    if server_type == _app_server_type.DEVELOPMENT:
        return DevelopmentConfig(_app_server_type.DEVELOPMENT)
    elif server_type == _app_server_type.PRODUCTION:
        return ProductionConfig(_app_server_type.PRODUCTION)
    return LocalConfig(_app_server_type.LOCAL)


class Config(object):
    """
    Set base configuration, env variable configuration and server configuration.
    """

    def __init__(self, server_type: str):
        self.SERVER_TYPE = server_type

    # The starting execution point of the app.
    FASTAPI_APP = "main.py"

    DEBUG: bool = False
    TESTING: bool = False

    DATABASE_URL = app_settings.DATABASE_URL
    ALEMBIC_DATABASE_URL = app_settings.ALEMBIC_DATABASE_URL
    HOST_URL = app_settings.HOST_URL
    HOST_PORT = app_settings.HOST_PORT
    LOG_LEVEL = app_settings.LOG_LEVEL
    JWT_SECRET_KEY = app_settings.JWT_SECRET_KEY
    JWT_REFRESH_SECRET_KEY = app_settings.JWT_REFRESH_SECRET_KEY
    AWS_ACCESS_KEY = app_settings.AWS_ACCESS_KEY
    AWS_SECRET_KEY = app_settings.AWS_SECRET_KEY
    AWS_REGION = app_settings.AWS_REGION
    AWS_BUCKET_NAME = app_settings.AWS_BUCKET_NAME
    S3_BUCKET_URL = app_settings.S3_BUCKET_URL
    SURPASS_API_BASE_URL = app_settings.SURPASS_API_BASE_URL
    SURPASS_TOKEN = app_settings.SURPASS_TOKEN
    WHITELIST_MOBILE_NUMBER = app_settings.WHITELIST_MOBILE_NUMBER
    SMTP_USER_EMAIL= app_settings.SMTP_USER_EMAIL
    SMTP_PASSWORD= app_settings.SMTP_PASSWORD
    IS_PROD = app_settings.IS_PROD
    RECIPIENT_ADMIN_EMAIL = app_settings.RECIPIENT_ADMIN_EMAIL
    RAZORPAY_KEY_ID= app_settings.RAZORPAY_KEY_ID
    RAZORPAY_SECRET=app_settings.RAZORPAY_SECRET
    GST_CHARGE = app_settings.GST_CHARGE


class LocalConfig(Config):
    """
    This class used to generate the config for the development instance.
    """
    DEBUG: bool = True
    TESTING: bool = True


class DevelopmentConfig(Config):
    """
    This class used to generate the config for the development instance.
    """
    DEBUG: bool = True
    TESTING: bool = True


class ProductionConfig(Config):
    """
    This class used to generate the config for the production instance.
    """


app_config = get_current_server_config()


class ConfigUtils:
    is_local_server = app_config.SERVER_TYPE == _app_server_type.LOCAL
    is_prod_server = app_config.SERVER_TYPE == _app_server_type.PRODUCTION
    is_development_server = app_config.SERVER_TYPE == _app_server_type.DEVELOPMENT


# Top level variable to be access for configs
config_utils = ConfigUtils()


class LogConfiguration:
    logger_name: str = "True Pay"
    logger_formatter: str = "%(asctime)s - %(levelname)s - %(name)s - %(process)d - %(filename)s|%(lineno)s:: %(funcName)s|%(lineno)s:: %(message)s"
    roll_over: str = "MIDNIGHT"
    backup_count: int = 90
    log_file_base_name: str = "log"
    log_file_base_dir: str = f"{os.getcwd()}/logs"
