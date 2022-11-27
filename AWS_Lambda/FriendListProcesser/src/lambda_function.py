import boto3
import json
import logging
import os
from common import entity, dynamodb
from datetime import datetime
from notion_client import Client

logger = logging.getLogger(__name__)


class NotionResource:
    def __init__(self, database_put_id: str, auth_token: str):
        self._client = Client(auth=auth_token)
        self._database_put_id = database_put_id

    def update(self, op: entity.OperationInfo, location: str) -> dict:
        target_info = op.info_new if op.action != entity.ActionType.REMOVE else op.info_old
        record = self._inline_find(target_info.user_id)
        if record is None:
            return self._inline_append(target_info, op.action == entity.ActionType.REMOVE, location)
        else:
            return self._inline_update(target_info, op.action == entity.ActionType.REMOVE, location, record)

    def _inline_find(self, user_id) -> dict:
        # 更新対象のレコードを取得
        query_res = self._client.databases.query(
            database_id=self._database_put_id,
            filter={"property": "user_id", "rich_text": {"equals": user_id}},
            page_size=1
        )
        if len(query_res["results"]) > 0:
            return query_res["results"][0]
        else:
            return None

    def _inline_append(self, value: entity.FriendInfo, mark_as_removed: bool, location: str) -> dict:
        res = self._client.pages.create(**{
            "parent": {
                "type": "database_id",
                "database_id": self._database_put_id
            },
            "properties": {
                "user_name": {
                    "type": "title",
                    "title": [{"type": "text", "text": {"content": value.user_name}}]
                },
                "user_name_displayed": {
                    "type": "rich_text",
                    "rich_text": [{"type": "text", "text": {"content": value.user_display_name}}]
                },
                "user_id": {
                    "type": "rich_text",
                    "rich_text": [{"type": "text", "text": {"content": value.user_id}}]
                },
                "location": {
                    "type": "rich_text",
                    "rich_text": [{"type": "text", "text": {"content": location or "(不明)"}}]
                },
                "regist_date": {
                    "type": "date",
                    "date": {"start": datetime.fromtimestamp(value.regist_date).strftime("%Y-%m-%d")} if value.regist_date is not None else None
                },
                "update_date": {
                    "type": "date",
                    "date": {"start": datetime.fromtimestamp(value.update_date).strftime("%Y-%m-%d")} if value.update_date is not None else None
                },
                "removed_date": {
                    "type": "date",
                    "date": {"start": datetime.fromtimestamp(value.update_date).strftime("%Y-%m-%d")} if mark_as_removed else None
                }
            }
        })
        return res

    def _inline_update(self, value: entity.FriendInfo, mark_as_removed: bool, location: str, page_obj: dict) -> dict:
        # レコードの情報を取得
        page_id = page_obj["id"]
        page_props = page_obj["properties"]

        # レコードの情報を更新
        # page_props["user_name"] = {
        #     "type": "title",
        #     "title": [{"type": "text", "text": {"content": value.user_name}}]
        # }
        page_props["user_name_displayed"] = {
            "type": "rich_text",
            "rich_text": [{"type": "text", "text": {"content": value.user_display_name}}]
        }
        # page_props["user_id"] = {
        #     "type": "rich_text",
        #     "rich_text": [{"type": "text", "text": {"content": value.user_id}}]
        # }
        # page_props["location"] = {
        #     "type": "rich_text",
        #     "rich_text": [{"type": "text", "text": {"content": location}}]
        # }
        # page_props["regist_date"] = {
        #     "type": "date",
        #     "date": {"start": datetime.fromtimestamp(value.regist_date).strftime("%Y-%m-%d")}
        # }
        page_props["update_date"] = {
            "type": "date",
            "date": {"start": datetime.fromtimestamp(value.update_date).strftime("%Y-%m-%d")} if value.update_date is not None else None
        }
        page_props["removed_date"] = {
            "type": "date",
            "date": {"start": datetime.fromtimestamp(value.update_date).strftime("%Y-%m-%d")} if mark_as_removed else None
        }

        # レコードの情報を反映
        res = self._client.pages.update(page_id, properties=page_props)
        return res

    def _inline_delete(self, page_id: str) -> dict:
        res = self._client.pages.update(page_id, archived=True)
        return res


class App:
    def __init__(self, dynamo: dynamodb.Service, notion: NotionResource):
        self._dynamo = dynamo
        self._notion = notion

    def invoke(self, op: entity.OperationInfo):
        if op.action == entity.ActionType.ADD:
            datetime_event = datetime.fromtimestamp(op.info_new.update_date)
            latest_encount = self._dynamo.find_first_activity(op.info_new, datetime_event)

            if latest_encount is not None:
                world_name = latest_encount.world_name
            else:
                world_name = "(不明)"

            self._notion.update(op, world_name)
        elif op.action == entity.ActionType.UPDATE or op.action == entity.ActionType.REMOVE:
            self._notion.update(op, None)


def lambda_handler(event, context):
    APP_GET_TABLE_NAME = os.getenv("APP_GET_TABLE_NAME")
    APP_PUT_TABLE_NAME = os.getenv("APP_PUT_TABLE_NAME")

    for job in event["Records"]:
        # キューイングされた情報を取得
        dec = entity.CustomJsonDecoder()
        job_info = json.loads(job["body"], object_hook=dec.object_hock)
        account_id, op_info = job_info["account_id"], job_info["event"]

        ses = boto3.Session()
        dynamo = dynamodb.Service(account_id, APP_GET_TABLE_NAME, APP_PUT_TABLE_NAME, ses, logger)
        meta = dynamo.get_app_metadata("notion")
        if meta is None:
            continue

        databaseid_friendlist = meta["databaseid_friendlist"]
        auth_token = meta["auth_token"]
        notion = NotionResource(databaseid_friendlist, auth_token)

        app = App(dynamo, notion)
        app.invoke(op_info)
