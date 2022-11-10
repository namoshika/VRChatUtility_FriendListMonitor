import boto3
import csv
import logging
from common import dynamodb, entity
from datetime import datetime

logger = logging.getLogger()


class AccountManager:
    def connect_vrchat(self, account: str, app_table: str, user_name: str, passwd: str) -> None:
        sess = boto3.Session()
        dynamo = dynamodb.Service(account, app_table, app_table, sess, logger)
        acc = dynamodb.AccountInfo(user_name, passwd, None)
        dynamo.put_account(acc, datetime.fromtimestamp(0))

    def disconnect_vrchat(self, account: str, app_table: str):
        sess = boto3.Session()
        dynamo = dynamodb.Service(account, app_table, app_table, sess, logger)
        dynamo.del_account()

    def connect_notion(self, account: str, app_table: str, auth_token: str, friendlist_dbid: str):
        sess = boto3.Session()
        dynamo = dynamodb.Service(account, app_table, app_table, sess, logger)
        dynamo.connect_app(
            "notion", {"auth_token": auth_token, "databaseid_friendlist": friendlist_dbid})

    def disconnect_notion(self, account: str, app_table: str):
        sess = boto3.Session()
        dynamo = dynamodb.Service(account, app_table, app_table, sess, logger)
        dynamo.disconnect_app("notion")


class FriendManager:
    def export_csv(self, account: str, app_table: str, path: str):
        sess = boto3.Session()
        dynamo = dynamodb.Service(account, app_table, app_table, sess, logger)
        friends = [["user_id", "user_name", "user_display_name", "regist_date", "update_date"]]
        friends.extend([
            [
                item.user_id,
                item.user_name,
                item.user_display_name,
                item.regist_date,
                item.update_date
            ] for item in dynamo.get_friends()
        ])
        with open(path, "w", encoding="utf8") as f:
            writer = csv.writer(f, delimiter="\t", lineterminator="\n")
            writer.writerows(friends)

    def import_csv(self, account: str, app_table: str, path: str):
        with open(path, "r", encoding="utf8") as f:
            friends = csv.DictReader(f, delimiter="\t", lineterminator="\n")
            friends = [entity.FriendInfo.from_dict(item) for item in friends]

        sess = boto3.Session()
        dynamo = dynamodb.Service(account, app_table, app_table, sess, logger)
        for item in friends:
            dynamo.put_friend(entity.OperationInfo(entity.ActionType.MIGRATION, item, None))

    def clear_all(self, account: str, app_table: str):
        sess = boto3.Session()
        dynamo = dynamodb.Service(account, app_table, app_table, sess, logger)
        friends = dynamo.get_friends()

        for item in friends:
            dynamo.put_friend(entity.OperationInfo(entity.ActionType.REMOVE, None, item))


class App:
    def __init__(self):
        self.account = AccountManager()
        self.friend = FriendManager()
