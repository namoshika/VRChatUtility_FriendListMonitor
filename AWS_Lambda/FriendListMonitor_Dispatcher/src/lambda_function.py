import logging
import os
from common import dynamodb, sqs
from datetime import datetime

logger = logging.getLogger(__name__)


class App:
    def __init__(self, app_get_table_name: str, worker_put_queue: str, dispatch_cooldown_sec: int, dispatch_count_limit: int):
        self._app_get_table_name = app_get_table_name
        self._worker_put_queue = worker_put_queue
        self._dispatch_cooldown_sec = dispatch_cooldown_sec
        self._dispatch_count_limit = dispatch_count_limit

    def invoke(self):
        current_date = datetime.now()
        queue = sqs.WorkerService(self._worker_put_queue, logger)
        accounts = dynamodb.Service.get_accounts(
            self._app_get_table_name, current_date,
            self._dispatch_cooldown_sec, self._dispatch_count_limit
        )

        for account_id in accounts:
            queue.enqueue(account_id)


def lambda_handler(event, context):
    APP_GET_TABLE_NAME = os.getenv("APP_GET_TABLE_NAME")
    DISPATCH_COOLDOWN_SEC = int(os.getenv("DISPATCH_COOLDOWN_SEC"))
    DISPATCH_COUNT_LIMIT = int(os.getenv("DISPATCH_COUNT_LIMIT"))
    WORKER_PUT_QUEUE = os.getenv("WORKER_PUT_QUEUE")

    app = App(APP_GET_TABLE_NAME, WORKER_PUT_QUEUE, DISPATCH_COOLDOWN_SEC, DISPATCH_COUNT_LIMIT)
    app.invoke()
