import logging
from typing import Optional, Type
import sys
import time

from pytglib import VERSION
from pytglib.client import Telegram
from pytglib.utils import AsyncResult
from pytglib.worker import BaseWorker
import telegram


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
logger.addHandler(handler)


class TgClient(Telegram):

    def __init__(
            self,
            api_id: int,
            api_hash: str,
            database_encryption_key: str,
            phone: str = None,
            bot_token: str = None,
            library_path: str = None,
            worker: Optional[Type[BaseWorker]] = None,
            files_directory: str = None,
            use_test_dc: bool = False,
            use_message_database: bool = True,
            device_model: str = 'python-telegram',
            application_version: str = VERSION,
            system_version: str = 'unknown',
            system_language_code: str = 'en',
            login: bool = False,
            default_workers_queue_size=1000,
            tdlib_verbosity: int = 2,
            bot: telegram.Bot = None,
            bot_owner: str = None,
    ) -> None:
        self.bot = bot
        self.bot_owner = bot_owner
        self.authorization_state = None
        super(TgClient, self).__init__(api_id=api_id, api_hash=api_hash,
                                       database_encryption_key=database_encryption_key,
                                       phone=phone, bot_token=bot_token,
                                       library_path=library_path, worker=worker,
                                       files_directory=files_directory,
                                       use_test_dc=use_test_dc,
                                       use_message_database=use_message_database,
                                       device_model=device_model,
                                       application_version=application_version,
                                       system_version=system_version,
                                       system_language_code=system_language_code,
                                       login=login,
                                       default_workers_queue_size=default_workers_queue_size,
                                       tdlib_verbosity=tdlib_verbosity)

    def _send_data(self, data: dict, result_id: str = None) -> AsyncResult:
        if '@extra' not in data:
            data['@extra'] = {}

        if not result_id and 'request_id' in data['@extra']:
            result_id = data['@extra']['request_id']

        async_result = AsyncResult(client=self, result_id=result_id)
        data['@extra']['request_id'] = async_result.id

        self._tdjson.send(data)
        self._results[async_result.id] = async_result
        async_result.request = data

        return async_result

    def _create_result(self, data: dict, result_id: str = None) -> AsyncResult:
        if '@extra' not in data:
            data['@extra'] = {}

        if not result_id and 'request_id' in data['@extra']:
            result_id = data['@extra']['request_id']

        async_result = AsyncResult(client=self, result_id=result_id)
        data['@extra']['request_id'] = async_result.id

        self._results[async_result.id] = async_result
        async_result.request = data

        return async_result

    def ready_send(self, field, value):
        async_result = self._results['updateAuthorizationState']
        async_result.request[field] = value
        logger.info('Sending to TG: %s', async_result.request)
        self._tdjson.send(async_result.request)

    def _send_telegram_code(self) -> AsyncResult:
        data = {'@type': 'checkAuthenticationCode'}

        self.bot.send_message(chat_id=self.bot_owner, text='code?')
        self.authorization_state = 'Idle'

        return self._create_result(data, result_id='updateAuthorizationState')

    def _send_password(self) -> AsyncResult:
        data = {'@type': 'checkAuthenticationPassword'}

        self.bot.send_message(chat_id=self.bot_owner, text='{} password?')
        self.authorization_state = 'Idle'

        return self._create_result(data, result_id='updateAuthorizationState')

    def _idle(self):
        time.sleep(0.01)

    def login_async(self):
        """
        Login process (blocking)
        Must be called before any other call. It sends initial params to the tdlib, sets database encryption key, etc.
        """
        actions = {
            None: self._send_encryption_key,
            'Idle': self._idle,
            'authorizationStateWaitTdlibParameters': self._set_initial_params,
            'authorizationStateWaitEncryptionKey': self._send_encryption_key,
            'authorizationStateWaitPhoneNumber': self._send_phone_number_or_bot_token,
            'authorizationStateWaitCode': self._send_telegram_code,
            'authorizationStateWaitPassword': self._send_password,
            'authorizationStateReady': self._complete_authorization,
        }
        if not self._authorized:
            actions[self.authorization_state]()

    def _listen_to_td(self):
        logger.info('[pytglib.td_listener] started')

        while self._is_enabled:
            update = self._tdjson.receive()

            logger.debug('Update: %s', update)

            if update:
                self._update_async_result(update)
                self._run_handlers(update)

    def _update_async_result(self, update: dict) -> Optional[AsyncResult]:
        async_result = None

        _special_types = (
            'updateAuthorizationState',
        )  # for authorizationProcess @extra.request_id doesn't work

        if update.get('@type') in _special_types:
            request_id = update['@type']
        else:
            request_id = update.get('@extra', {}).get('request_id')

        if not request_id:
            logger.debug('request_id has not been found in the update')
        else:
            async_result = self._results.get(request_id)

        if not async_result:
            logger.debug('async_result has not been found in by request_id=%s', request_id)
        else:
            if update['@type'] == 'updateAuthorizationState':
                self.authorization_state = update['authorization_state']['@type']
            elif update['@type'] == 'error':
                if update['message'] == 'Database encryption key is needed: call checkDatabaseEncryptionKey first':
                    self.authorization_state = 'authorizationStateWaitEncryptionKey'
                elif update['message'] == 'Initialization parameters are needed: call setTdlibParameters first':
                    self.authorization_state = 'authorizationStateWaitTdlibParameters'
            async_result.parse_update(update)
            self._results.pop(request_id, None)

        return async_result
