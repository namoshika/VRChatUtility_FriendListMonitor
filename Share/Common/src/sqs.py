import boto3
import logging
from .entity import *

sqs = boto3.resource("sqs")


class WorkerService:
    def __init__(self, put_queue: str, logger: logging.Logger):
        self._put_queue = put_queue
        self._logger = logger

    def enqueue(self, account_id: str):
        job_info = {"account_id": account_id}
        job_json = json.dumps(job_info, ensure_ascii=False)
        queue = sqs.get_queue_by_name(QueueName=self._put_queue)
        queue.send_message(
            MessageBody=job_json,
            MessageAttributes={"Type": {"DataType": "String", "StringValue": "InvokeFunction"}}
        )

    def dequeue(self):
        queue = sqs.get_queue_by_name(QueueName=self._put_queue)
        messages = queue.receive_messages(
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
            MaxNumberOfMessages=10
        )
        for msg in messages:
            msg.delete()


class ProcesserService:
    def __init__(self, account_id: str, put_queue: str, logger: logging.Logger):
        self._account_id = account_id
        self._put_queue = put_queue
        self._logger = logger

    def enqueue(self, op: OperationInfo):
        job_json = json.dumps({"account_id": self._account_id, "event": op}, ensure_ascii=False, cls=CustomJsonEncoder)
        queue = sqs.get_queue_by_name(QueueName=self._put_queue)
        queue.send_message(
            MessageBody=job_json,
            MessageAttributes={"Type": {"DataType": "String", "StringValue": "InvokeFunction"}}
        )
