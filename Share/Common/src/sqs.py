import boto3
import logging
from .entity import *


class WorkerService:
    def __init__(self, account_id: str, put_queue: str, sess: boto3.Session, logger: logging.Logger):
        self._account_id = account_id
        self._put_queue = put_queue
        self._logger = logger
        self._sqs = sess.resource("sqs")

    def enqueue(self):
        job_info = {"account_id": self._account_id}
        job_json = json.dumps(job_info, ensure_ascii=False)
        queue = self._sqs.get_queue_by_name(QueueName=self._put_queue)
        queue.send_message(
            MessageBody=job_json,
            MessageAttributes={"Type": {"DataType": "String", "StringValue": "InvokeFunction"}}
        )

    def recieve(self) -> list:
        queue = self._sqs.get_queue_by_name(QueueName=self._put_queue)
        messages = queue.receive_messages(
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
            MaxNumberOfMessages=10
        )
        # for msg in messages:
        #     msg.delete()
        return messages


class ProcesserService:
    def __init__(self, account_id: str, put_queue: str, sess: boto3.Session, logger: logging.Logger):
        self._account_id = account_id
        self._put_queue = put_queue
        self._logger = logger
        self._sqs = sess.resource("sqs")

    def enqueue(self, op: OperationInfo):
        job_json = json.dumps({"account_id": self._account_id, "event": op}, ensure_ascii=False, cls=CustomJsonEncoder)
        queue = self._sqs.get_queue_by_name(QueueName=self._put_queue)
        queue.send_message(
            MessageBody=job_json,
            MessageAttributes={"Type": {"DataType": "String", "StringValue": "InvokeFunction"}}
        )

    def recieve(self) -> list:
        queue = self._sqs.get_queue_by_name(QueueName=self._put_queue)
        messages = queue.receive_messages(
            AttributeNames=["All"],
            MessageAttributeNames=["All"],
            MaxNumberOfMessages=10
        )
        # for msg in messages:
        #     msg.delete()
        return messages
