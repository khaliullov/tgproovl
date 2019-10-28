import logging
import threading
from queue import Queue


logger = logging.getLogger(__name__)


class TgproovlWorker:
    """Simple one-thread worker"""

    def __init__(self, queue: Queue, timeout: int = 10) -> None:
        self._is_enabled = True
        self._queue = queue
        self._timeout = timeout

    def run(self) -> None:
        self._thread = threading.Thread(target=self._run_thread)    # pylint: disable=attribute-defined-outside-init
        self._thread.daemon = True
        self._thread.start()

    def _run_thread(self) -> None:
        logger.info('[TgproovlWorker] started')

        while self._is_enabled:
            handler, update = self._queue.get()
            try:
                failed = not handler(update)
            except Exception as exc:
                failed = str(exc)
            if failed:
                attempt = update.get('try', 0)
                attempt += 1
                if attempt > 5:
                    logger.error('Giving up doing task with type %s %s %s',
                                 str(handler), failed, update)
                else:
                    update['try'] = attempt
                    self._queue.put((handler, update), timeout=self._timeout)
            self._queue.task_done()
