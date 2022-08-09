import boto3
import datetime
import json
import logging
import os
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)


class DbResource:
    dynamodb_res = boto3.resource("dynamodb")

    def __init__(self, get_table_name: str, put_table_name: str):
        self._get_table = DbResource.dynamodb_res.Table(get_table_name)
        self._put_table = DbResource.dynamodb_res.Table(put_table_name)

    def get_monitoring_accounts(self, current_date: datetime.datetime, cooldown_sec: int, limit: int):
        unixtime_higher = int(current_date.timestamp())
        unixtime_higher = unixtime_higher - cooldown_sec
        params = {
            "Select": "ALL_ATTRIBUTES",
            "KeyConditionExpression": Key("pk").eq("#app:monitoring_accounts"),
            "FilterExpression": Attr("update_date").lt(unixtime_higher),
        }
        if limit > 0:
            params["Limit"] = limit
        count = 0
        while limit == 0 or count < limit:
            res_api = self._get_table.query(**params)
            for item in res_api["Items"]:
                yield item["user_id"]
                count += 1

            # 続きが無ければ処理終了
            if "LastEvaluatedKey" not in res_api:
                break
            # 続きがあれば次のAPI呼び出し時に開始キーを追加
            params["ExclusiveStartKey"] = res_api["LastEvaluatedKey"]


class App:
    def __init__(self, WORKER_put_queue: str, dispatch_cooldown_sec: int, dispatch_count_limit: int, app_db: DbResource):
        self._app_db = app_db
        self._WORKER_put_queue = WORKER_put_queue
        self._dispatch_cooldown_sec = dispatch_cooldown_sec
        self._dispatch_count_limit = dispatch_count_limit

    def invoke(self):
        current_date = datetime.datetime.now()
        accounts = self._app_db.get_monitoring_accounts(
            current_date, self._dispatch_cooldown_sec, self._dispatch_count_limit)

        for user_id in accounts:
            job_info = {"user_id": user_id}
            job_json = json.dumps(job_info, ensure_ascii=False)

            sqs = boto3.resource("sqs")
            vfe_queue = sqs.get_queue_by_name(
                QueueName=self._WORKER_put_queue)
            vfe_queue.send_message(
                MessageBody=job_json,
                MessageAttributes={
                    "Type": {"DataType": "String", "StringValue": "InvokeFunction"}
                }
            )

        # vfe_messages = vfe_queue.receive_messages(
        #     AttributeNames=["All"],
        #     MessageAttributeNames=["All"],
        #     MaxNumberOfMessages=10
        # )
        # for msg in vfe_messages:
        #     msg.delete()


def lambda_handler(event, context):
    APP_GET_TABLE_NAME = os.getenv("APP_GET_TABLE_NAME")
    APP_PUT_TABLE_NAME = os.getenv("APP_PUT_TABLE_NAME")
    DISPATCH_COOLDOWN_SEC = int(os.getenv("DISPATCH_COOLDOWN_SEC"))
    DISPATCH_COUNT_LIMIT = int(os.getenv("DISPATCH_COUNT_LIMIT"))
    WORKER_PUT_QUEUE = os.getenv("WORKER_PUT_QUEUE")

    res_db = DbResource(APP_GET_TABLE_NAME, APP_PUT_TABLE_NAME)
    app = App(
        WORKER_PUT_QUEUE, DISPATCH_COOLDOWN_SEC, DISPATCH_COUNT_LIMIT,
        res_db
    )
    app.invoke()
