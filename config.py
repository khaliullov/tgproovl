import os


class MainConfig(object):
    DEBUG = bool(os.environ.get('TGPROOVL_DEBUG', False))
    APPLICATION_ROOT = os.environ.get('TGPROOVL_URL_PATH_PREFIX', '/')
    PREFERRED_URL_SCHEME = os.environ.get('TGPROOVL_URL_SCHEME', 'https')
    SERVER_NAME = os.environ.get('TGPROOVL_URL_HOST', 'bot.example.com')
    FLASK_RUN_HOST = os.environ.get('TGPROOVL_HOST', '0.0.0.0')
    FLASK_RUN_PORT = int(os.environ.get('TGPROOVL_PORT', 8080))
    TELEGRAM_TOKEN = os.environ.get('TGPROOVL_TELEGRAM_TOKEN', '<token>')
    PERSISTENCE_PATH = os.environ.get('TGPROOVL_PERSISTENCE_PATH',
                                      '/tmp/tgproovl.state')
    TELEGRAM_WORKERS = int(os.environ.get('TGPROOVL_TELEGRAM_WORKERS', 4))
    BOT_PASSWORD = os.environ.get('TGPROOVL_BOT_PASSWORD', '')
    SECRET_KEY = os.environ.get('TGPROOVL_SECRET_KEY', '<secret_key>').encode('ascii')
    PROOVL_USER = os.environ.get('TGPROOVL_PROOVL_USER', '')
    PROOVL_TOKEN = os.environ.get('TGPROOVL_PROOVL_TOKEN', '')
    PROOVL_TARIFF = int(os.environ.get('TGPROOVL_PROOVL_TARIFFT', 2))
    TELEGRAM_CLI_HOST = os.environ.get('TGPROOVL_TELEGRAM_CLI_HOST', '127.0.0.1')
    TELEGRAM_CLI_PORT = int(os.environ.get('TGPROOVL_TELEGRAM_CLI_PORT', 2391))
    TELEGRAM_DEVELOPER = int(os.environ.get('TGPROOVL_TELEGRAM_DEVELOPER', -1))
    TELEGRAM_OWNER = int(os.environ.get('TGPROOVL_TELEGRAM_OWNER', -1))
    TELEGRAM_PHONE = os.environ.get('TGPROOVL_TELEGRAM_PHONE', '')
    TELEGRAM_API_ID = os.environ.get('TGPROOVL_TELEGRAM_API_ID', '')
    TELEGRAM_API_HASH = os.environ.get('TGPROOVL_TELEGRAM_API_HASH', '')
    SMS_HALF_TIMEOUT = int(os.environ.get('TGPROOVL_SMS_HALF_TIMEOUT', 900))
    CHAT_HALF_TIMEOUT = int(os.environ.get('TGPROOVL_CHAT_HALF_TIMEOUT', 1800))
