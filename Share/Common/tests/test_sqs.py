import boto3
import json
import logging
import os
import sys


class TestWorkerService:
    def test_crud(self):
        sys.path.append("src")
        from src import sqs

        logger = logging.getLogger(__name__)
        target = sqs.WorkerService(
            "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            os.getenv("WORKER_PUT_QUEUE"),
            boto3.Session(),
            logger
        )

        target.enqueue()
        res = target.recieve()
        assert len(res) > 0

        res = res[0]
        res_body = json.loads(res.body)
        assert res_body["account_id"] == "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

        res.delete()


class TestProcesserService:
    def test_crud(self):
        sys.path.append("src")
        from src import entity, sqs

        logger = logging.getLogger(__name__)
        target = sqs.ProcesserService(
            "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            os.getenv("PROCESSER_PUT_QUEUE"),
            boto3.Session(),
            logger
        )

        target.enqueue(
            entity.OperationInfo(
                entity.ActionType.ADD,
                entity.FriendInfo("ユーザID", "ユーザ名", "ユーザ表示名", 0, 0),
                None
            )
        )
        res = target.recieve()
        assert len(res) > 0

        res = res[0]
        dec = entity.CustomJsonDecoder()
        res_body = json.loads(res.body, object_hook=dec.object_hock)
        assert res_body["account_id"] == "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        assert isinstance(res_body["event"], entity.OperationInfo)

        res.delete()
