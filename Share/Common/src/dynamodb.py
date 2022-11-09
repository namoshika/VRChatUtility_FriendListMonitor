import boto3
import logging
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from http.cookiejar import CookieJar, MozillaCookieJar
from boto3.dynamodb.conditions import Key, Attr
from .entity import *

@dataclass
class AccountInfo:
    vrchat_user_name: str
    vrchat_passwd: str
    cookies: CookieJar


class Service:
    SUFFIX_LEN: int = 3

    def __init__(self, account_id: str, get_table_name: str, put_table_name: str, aws_sess: boto3.Session, logger: logging.Logger):
        self._account_id = account_id
        self._dynamodb = aws_sess.client("dynamodb")
        self._dynamodb_res = aws_sess.resource("dynamodb")
        self._get_table = self._dynamodb_res.Table(get_table_name)
        self._put_table = self._dynamodb_res.Table(put_table_name)
        self._logger = logger

    def put_account(self, info: AccountInfo, update_date: datetime = None) -> None:
        update_unixtime = int(update_date.timestamp()) if update_date is not None else None
        cookies_txt = self.cookiejar2text(info.cookies) if info.cookies is not None else None

        # 更新式を作成
        exp_update = "SET "
        exp_base = {
            "vrchat_user_id": self._account_id,
            "vrchat_user_name": info.vrchat_user_name,
            "vrchat_passwd": info.vrchat_passwd,
            "cookies": cookies_txt,
            "update_date": update_unixtime
        }
        exp_base = [(key, val) for key, val in exp_base.items() if val is not None]
        exp_update = ", ".join([f"{key} = :{key}_val" for key, _ in exp_base])
        if exp_update == "":
            return
        exp_update = f"SET {exp_update}"
        exp_values = {f":{key}_val": val for key, val in exp_base}

        # 更新クエリを実行
        self._put_table.update_item(
            Key={
                "pk": "#app:monitoring_accounts",
                "sk": f"#account:{self._account_id}"
            },
            UpdateExpression=exp_update,
            ExpressionAttributeValues=exp_values
        )

    def get_account(self) -> AccountInfo:
        res_api = self._get_table.get_item(Key={
            "pk": "#app:monitoring_accounts",
            "sk": f"#account:{self._account_id}"
        })
        res_api = res_api["Item"]
        vrchat_user_name = res_api["vrchat_user_name"]
        vrchat_passwd = res_api["vrchat_passwd"]
        cookies = self.text2cookiejar(res_api["cookies"]) if "cookies" in res_api else MozillaCookieJar()
        return AccountInfo(vrchat_user_name, vrchat_passwd, cookies)

    def del_account(self) -> None:
        self._get_table.delete_item(Key={
            "pk": "#app:monitoring_accounts",
            "sk": f"#account:{self._account_id}"
        })

    def connect_app(self, app_name: str, metadata: dict[str, str]):
        # 更新式を作成
        exp_update = "SET "
        exp_base = [(key, val) for key, val in metadata.items() if val is not None]
        exp_update = ", ".join([f"{key} = :{key}_val" for key, _ in exp_base])
        if exp_update == "":
            return
        exp_update = f"SET {exp_update}"
        exp_values = {f":{key}_val": val for key, val in exp_base}

        # 更新クエリを実行
        self._put_table.update_item(
            Key={
                "pk": f"#account:{self._account_id}",
                "sk": f"#connect:{app_name}"
            },
            UpdateExpression=exp_update,
            ExpressionAttributeValues=exp_values
        )

    def get_app_metadata(self, app_name: str) -> dict[str, str]:
        res_api = self._get_table.get_item(Key={
            "pk": f"#account:{self._account_id}",
            "sk": f"#connect:{app_name}"
        })
        res_api = res_api.get("Item")
        if res_api is None:
            return None

        del res_api["pk"], res_api["sk"]
        return res_api

    def disconnect_app(self, app_name: str) -> None:
        self._put_table.delete_item(
            Key={
                "pk": f"#account:{self._account_id}",
                "sk": f"#connect:{app_name}"
            }
        )

    def get_friends(self) -> list[FriendInfo]:
        db_res = self._get_table.query(
            KeyConditionExpression="pk = :pk and begins_with(sk, :sk)",
            ExpressionAttributeValues={
                ":pk": f"#account:{self._account_id}",
                ":sk": "#friend:"
            }
        )
        friend_infos = [
            FriendInfo(
                item["user_id"], item["user_name"], item["user_display_name"],
                item.get("regist_date"), item["update_date"]) for item in db_res["Items"]
        ]
        return friend_infos

    def put_friend(self, op: OperationInfo) -> None:
        # 失敗した場合には再試行。2回失敗した場合は catch 句で中断させる
        for i in range(2):
            try:
                if op.action == ActionType.MIGRATION:
                    self._put_table.put_item(
                        Item={
                            "pk": f"#account:{self._account_id}",
                            "sk": f"#friend:{op.info_new.user_id}",
                            "user_id": op.info_new.user_id,
                            "user_name": op.info_new.user_name,
                            "user_display_name": op.info_new.user_display_name,
                            "regist_date": op.info_new.regist_date,
                            "update_date": op.info_new.update_date
                        }
                    )
                elif op.action == ActionType.ADD:
                    self._put_table.put_item(
                        Item={
                            "pk": f"#account:{self._account_id}",
                            "sk": f"#friend:{op.info_new.user_id}",
                            "user_id": op.info_new.user_id,
                            "user_name": op.info_new.user_name,
                            "user_display_name": op.info_new.user_display_name,
                            "regist_date": op.info_new.update_date,
                            "update_date": op.info_new.update_date
                        }
                    )
                elif (op.action == ActionType.UPDATE):
                    self._put_table.put_item(
                        Item={
                            "pk": f"#account:{self._account_id}",
                            "sk": f"#friend:{op.info_new.user_id}",
                            "user_id": op.info_new.user_id,
                            "user_name": op.info_new.user_name,
                            "user_display_name": op.info_new.user_display_name,
                            "regist_date": op.info_old.regist_date,
                            "update_date": op.info_new.update_date
                        }
                    )
                elif (op.action == ActionType.REMOVE):
                    self._put_table.delete_item(
                        Key={
                            "pk": f"#account:{self._account_id}",
                            "sk": f"#friend:{op.info_old.user_id}"
                        }
                    )
                else:
                    raise Exception("想定外のエラーが発生しました")

                time.sleep(0.1)
                break
            except self._dynamodb.exceptions.ProvisionedThroughputExceededException as ex:
                time.sleep(10)
                self._logger.warning("キャパシティ超過")

    def put_activity(self, activity: LogEvent) -> None:
        timestamp_id = activity.timestamp.strftime("%Y%m%d_%H%M%S")
        timestamp_text = activity.timestamp.strftime("%Y.%m.%d %H:%M:%S")
        # レコード有効期限を秒単位の UNIXTIME として生成
        expiration_time = datetime.now()
        expiration_time = expiration_time + timedelta(hours=24)
        expiration_time = int(expiration_time.timestamp())

        i = 0
        while True:
            try:
                if isinstance(activity, LogEventEnterWorld):
                    val_sk = f"#activity:world.enter#timestamp:{timestamp_id}"
                    val_suffix = sum(val_sk.encode()) % self.SUFFIX_LEN
                    self._put_table.put_item(Item={
                        "pk": f"#account:{self._account_id}#suffix:{val_suffix}",
                        "sk": val_sk,
                        "instance_id": activity.instance_id,
                        "world_id": activity.world_id,
                        "world_name": activity.world_name,
                        "timestamp": timestamp_text,
                        "expiration_time": expiration_time
                    })
                elif isinstance(activity, LogEventLeftWorld):
                    val_sk = f"#activity:world.left#timestamp:{timestamp_id}"
                    val_suffix = sum(val_sk.encode()) % self.SUFFIX_LEN
                    self._put_table.put_item(Item={
                        "pk": f"#account:{self._account_id}#suffix:{val_suffix}",
                        "sk": val_sk,
                        "instance_id": activity.instance_id,
                        "world_id": activity.world_id,
                        "world_name": activity.world_name,
                        "timestamp": timestamp_text,
                        "expiration_time": expiration_time
                    })
                elif isinstance(activity, LogEventEnterPlayer):
                    username_esc = activity.user_display_name
                    username_esc = username_esc.replace("\\", "\\\\")
                    username_esc = username_esc.replace("#", "\\u0023")
                    username_esc = username_esc.replace(":", "\\u003a")
                    val_sk = f"#activity:user.enter.{username_esc}#timestamp:{timestamp_id}"
                    val_suffix = sum(val_sk.encode()) % self.SUFFIX_LEN
                    self._put_table.put_item(Item={
                        "pk": f"#account:{self._account_id}#suffix:{val_suffix}",
                        "sk": val_sk,
                        "instance_id": activity.instance_id,
                        "world_id": activity.world_id,
                        "world_name": activity.world_name,
                        "user_display_name": activity.user_display_name,
                        "timestamp": timestamp_text,
                        "expiration_time": expiration_time
                    })
                elif isinstance(activity, LogEventLeftPlayer):
                    username_esc = activity.user_display_name
                    username_esc = username_esc.replace("\\", "\\\\")
                    username_esc = username_esc.replace("#", "\\u0023")
                    username_esc = username_esc.replace(":", "\\u003a")
                    val_sk = f"#activity:user.left.{username_esc}#timestamp:{timestamp_id}"
                    val_suffix = sum(val_sk.encode()) % self.SUFFIX_LEN
                    self._put_table.put_item(Item={
                        "pk": f"#account:{self._account_id}#suffix:{val_suffix}",
                        "sk": val_sk,
                        "instance_id": activity.instance_id,
                        "world_id": activity.world_id,
                        "world_name": activity.world_name,
                        "user_display_name": activity.user_display_name,
                        "timestamp": timestamp_text,
                        "expiration_time": expiration_time
                    })
                break
            except self.dynamodb.exceptions.ProvisionedThroughputExceededException as ex:
                if i > 1:
                    self._logger.warning("DynamoDB 書き込みでキャパシティ超過を起因とした複数回のエラーが発生.")
                    raise
                else:
                    self._logger.warning("DynamoDB 書き込みでキャパシティ超過を起因とした複数回のエラーが発生 (10秒後に再試行).")
                    time.sleep(10)

    def find_latest_activity(self, target: FriendInfo, max_datetime: datetime) -> LogEventEnterPlayer:
        res = list()
        for suffix in range(self.SUFFIX_LEN):
            max_datetime_txt = (max_datetime + timedelta(seconds=1)).strftime("%Y%m%d_%H%M%S")
            pk = f"#account:{self._account_id}#suffix:{suffix}"
            sk1 = f"#activity:user.enter.{target.user_display_name}#timestamp:00000000_000000"
            sk2 = f"#activity:user.enter.{target.user_display_name}#timestamp:{max_datetime_txt}"
            res_api = self._get_table.query(
                Select="ALL_ATTRIBUTES",
                KeyConditionExpression=Key("pk").eq(pk) & Key("sk").between(sk1, sk2),
                ScanIndexForward=False,
                Limit=1
            )
            res.extend(res_api["Items"])

        res = list(sorted(res, key=lambda val: val["timestamp"], reverse=True))
        if len(res) == 0:
            return None

        res = res[0]
        res = LogEventEnterPlayer(
            LogEventType.ENTER_PLAYER,
            datetime.strptime(res["timestamp"], "%Y.%m.%d %H:%M:%S"),
            res["instance_id"],
            res["world_id"],
            res["world_name"],
            res["user_display_name"]
        )
        return res

    @staticmethod
    def get_accounts(get_table_name: str, current_date: datetime, cooldown_sec: int, limit: int) -> str:
        dynamodb_res = boto3.resource("dynamodb")
        get_table = dynamodb_res.Table(get_table_name)

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
            res_api = get_table.query(**params)
            for item in res_api["Items"]:
                yield item["vrchat_user_id"]
                count += 1

            # 続きが無ければ処理終了
            if "LastEvaluatedKey" not in res_api:
                break
            # 続きがあれば次のAPI呼び出し時に開始キーを追加
            params["ExclusiveStartKey"] = res_api["LastEvaluatedKey"]

    @staticmethod
    def text2cookiejar(text: str) -> CookieJar:
        cookie_jar = MozillaCookieJar()
        if text != None:
            with tempfile.NamedTemporaryFile("w") as tmp:
                tmp.write(text)
                tmp.file.flush()
                cookie_jar.load(tmp.name)
        return cookie_jar

    @staticmethod
    def cookiejar2text(cookies: MozillaCookieJar) -> str:
        with tempfile.NamedTemporaryFile("r") as tmp:
            cookies.save(tmp.name)
            return tmp.read()
