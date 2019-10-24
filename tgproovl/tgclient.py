import logging
from typing import Optional, Type, Callable
import sys

from pytglib import VERSION
from pytglib.client import Telegram
from pytglib.utils import AsyncResult
from pytglib.worker import BaseWorker


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
    ) -> None:
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

        logger.info('Sending to TG: %s', data)
        self._tdjson.send(data)
        self._results[async_result.id] = async_result
        async_result.request = data

        return async_result

    def _listen_to_td(self):
        logger.info('[pytglib.td_listener] started')

        while self._is_enabled:
            update = self._tdjson.receive()

            logger.debug('Update: %s', update)

            if update:
                try:
                    self._update_async_result(update)
                except Exception:
                    if update.get('@type') == 'updateAuthorizationState':
                        request_id = update['@type']
                    else:
                        request_id = update.get('@extra', {}).get('request_id')
                    async_result = self._results.pop(request_id, None)
                    async_result.update = update
                self._run_handlers(update)

    def add_handler(self, event, func: Callable) -> None:
        """
        Adds function to handle all incoming messages
        Args:
            func (:obj:`Callable`):
                Message handler function
        """
        self.add_update_handler(event, func)
