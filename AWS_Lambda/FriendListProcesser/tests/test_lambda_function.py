import boto3
import json
import logging
import sys
import os
from datetime import datetime

sys.path.append("src")
logger = logging.getLogger(__name__)


class TestNotionResource:
    def test_update(self):
        from src import lambda_function
        from src.common import entity

        NOTION_AUTH_TOKEN = os.getenv("NOTION_AUTH_TOKEN")
        NOTION_PUT_DATABASEID_FRIENDLIST = os.getenv("NOTION_PUT_DATABASEID_FRIENDLIST")
        client = lambda_function.NotionResource(NOTION_PUT_DATABASEID_FRIENDLIST, NOTION_AUTH_TOKEN)
        now_time = int(datetime.now().timestamp())

        val = entity.OperationInfo(
            lambda_function.entity.ActionType.ADD,
            entity.UserInfo("user_id_01", "user_name_01", "user_display_name_01", 0, 0),
            None
        )
        res = client.update(val, "location_01")

        val = entity.OperationInfo(
            lambda_function.entity.ActionType.UPDATE,
            entity.UserInfo("user_id_01", "user_name_02", "user_display_name_02", now_time, now_time),
            entity.UserInfo("user_id_01", "user_name_01", "user_display_name_01", 0, 0)
        )
        res = client.update(val, "location_02")

        val = entity.OperationInfo(
            lambda_function.entity.ActionType.REMOVE,
            None,
            entity.UserInfo("user_id_01", "user_name_01", "user_display_name_01", 0, 0)
        )
        res = client.update(val, "location_03")
        client._inline_delete(res["id"])

    def test_inline_method(self):
        from src import lambda_function
        from src.common import entity

        NOTION_AUTH_TOKEN = os.getenv("NOTION_AUTH_TOKEN")
        NOTION_PUT_DATABASEID_FRIENDLIST = os.getenv("NOTION_PUT_DATABASEID_FRIENDLIST")

        val = entity.UserInfo("user_id_01", "user_name_01", "user_display_name_01", 0, 0)
        client = lambda_function.NotionResource(NOTION_PUT_DATABASEID_FRIENDLIST, NOTION_AUTH_TOKEN)
        res1 = client._inline_append(val, True, "location_01")
        assert res1 is not None
        res2 = client._inline_append(val, False, "location_01")
        assert res2 is not None

        client = lambda_function.NotionResource(NOTION_PUT_DATABASEID_FRIENDLIST, NOTION_AUTH_TOKEN)
        res = client._inline_find("user_id_01")
        assert res is not None

        now_time = int(datetime.now().timestamp())
        val = entity.UserInfo("user_id_02", "user_name_02", "user_display_name_02", now_time, now_time)
        res1 = client._inline_update(val, True, None, res1)
        assert res1 is not None
        res2 = client._inline_update(val, False, None, res2)
        assert res2 is not None

        res1 = client._inline_delete(res1["id"])
        assert res1 is not None
        res2 = client._inline_delete(res2["id"])
        assert res2 is not None


def test_handler_name_1():
    from src import lambda_function
    from src.common import entity, dynamodb

    ACCOUNT_ID = os.getenv("ACCOUNT_ID")
    APP_GET_TABLE_NAME = os.getenv("APP_GET_TABLE_NAME")
    APP_PUT_TABLE_NAME = os.getenv("APP_PUT_TABLE_NAME")
    dyn = dynamodb.Service(ACCOUNT_ID, APP_GET_TABLE_NAME, APP_PUT_TABLE_NAME, boto3.Session(), logger)
    dyn.put_activity(entity.LogEventEnterPlayer(
        entity.LogEventType.ENTER_PLAYER, datetime.fromtimestamp(1665694831),
        "インスタンスID", "ワールドID", "ワールド名", "ユーザ表示名")
    )
    events = {
        "Records": [
            {
                "body": json.dumps({
                    "account_id": ACCOUNT_ID,
                    "event": {
                        "_type": "OperationInfo",
                        "action": "ADD",
                        "info_new": {
                            "_type": "UserInfo",
                            "user_id": "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                            "user_name": "ユーザ名",
                            "user_display_name": "ユーザ表示名",
                            "regist_date": 1665694831,
                            "update_date": 1665694831
                        },
                        "info_old": None
                    }
                })
            }
        ]
    }
    lambda_function.lambda_handler(events, None)


def test_handler_name_2():
    from src import lambda_function

    ACCOUNT_ID = os.getenv("ACCOUNT_ID")
    events = {
        "Records": [
            {
                "body": json.dumps({
                    "account_id": ACCOUNT_ID,
                    "event":
                    {
                        "_type": "OperationInfo",
                        "action": "UPDATE",
                        "info_new":
                        {
                            "_type": "UserInfo",
                            "user_id": "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                            "user_name": "ユーザ名 (更新後)",
                            "user_display_name": "ユーザ表示名 (更新後)",
                            "regist_date": 1661942977,
                            "update_date": 1667120431,
                        },
                        "info_old":
                        {
                            "_type": "UserInfo",
                            "user_id": "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                            "user_name": "ユーザ名",
                            "user_display_name": "ユーザ表示名",
                            "regist_date": 1661942977,
                            "update_date": 1661942977,
                        },
                    }
                })
            }
        ]
    }
    lambda_function.lambda_handler(events, None)


def test_handler_name_3():
    from src import lambda_function

    ACCOUNT_ID = os.getenv("ACCOUNT_ID")
    events = {
        "Records": [
            {
                "body": json.dumps({
                    "account_id": ACCOUNT_ID,
                    "event":
                    {
                        "_type": "OperationInfo",
                        "action": "REMOVE",
                        "info_new": None,
                        "info_old":
                        {
                            "_type": "UserInfo",
                            "user_id": "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
                            "user_name": "ユーザ名 (更新後)",
                            "user_display_name": "ユーザ表示名 (更新後)",
                            "regist_date": 1661942977,
                            "update_date": 1667120431,
                        },
                    }
                })
            }
        ]
    }
    lambda_function.lambda_handler(events, None)
