import base64
import boto3
import datetime
import enum
import json
import logging
import os
import tempfile
import time
import typing
from dataclasses import dataclass
from http.cookiejar import CookieJar, MozillaCookieJar
from urllib import request, parse, error

logger = logging.getLogger(__name__)


class ActionType(enum.Enum):
    Add = enum.auto()
    Update = enum.auto()
    Remove = enum.auto()


@dataclass
class FriendInfo:
    user_id: str
    user_name: str
    user_display_name: str
    regist_date: int
    update_date: int


@dataclass
class OperationInfo:
    action_type: ActionType
    info_new: FriendInfo
    info_old: FriendInfo


class CustomJsonEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, FriendInfo):
            return {
                "_type": "FriendInfo",
                "user_id": o.user_id,
                "user_name": o.user_name,
                "user_display_name": o.user_display_name,
                "regist_date": int(o.regist_date) if o.regist_date is not None else None,
                "update_date": int(o.update_date) if o.update_date is not None else None
            }
        elif isinstance(o, OperationInfo):
            return {
                "_type": "OperationInfo",
                "action_type": o.action_type.name,
                "info_new": o.info_new,
                "info_old": o.info_old
            }
        else:
            return super().default(o)


class CustomJsonDecoder(json.JSONDecoder):
    def object_hock(self, o):
        if "_type" not in o:
            return o

        typ = o["_type"]
        if typ == "FriendInfo":
            return FriendInfo(
                o["user_id"], o["user_name"], o["user_display_name"],
                o["regist_date"], o["update_date"])
        if typ == "OperationInfo":
            return OperationInfo(
                ActionType(o["action_type"]), o["info_new"], o["info_old"])


class VRChatResource:
    ENDPOINT_URL = "https://api.vrchat.cloud/api/1"
    APIKEY = "JlE5Jldo5Jibnk5O5hTx6XVqsJu4WJ26"

    def __init__(self, cookie_jar: CookieJar) -> None:
        opener = request.build_opener(request.HTTPCookieProcessor(cookie_jar))
        opener.addheaders = [
            ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"),
            ("Accept", "application/json")
        ]
        self._opener = opener

    def get_current_user(self, vrc_username: str, vrc_passwd: str):
        headers: dict[str, str] = dict()
        for i in range(2):
            try:
                api_res = self._internal_get_current_user(headers)
                return api_res
            except error.HTTPError as e:
                if (i == 0 and e.status == 401):
                    headers["Authorization"] = "Basic " + base64.b64encode(
                        f"{vrc_username}:{vrc_passwd}".encode("utf8")).decode("utf8")
                else:
                    raise

    def get_friends(self, current_user_info, update_time: datetime.datetime) -> list[FriendInfo]:
        # 認証情報とフレンドID一覧を取得
        friend_ids: list[str] = current_user_info["friends"]
        friend_ids.sort()

        # フレンドの表示名を取得
        update_time = int(update_time.timestamp())
        friends_map = dict()
        friends_max_length = 100
        friendsOffset = 0

        # 取得 (オンライン)
        friendsOffset = 0
        while True:
            apiRes = self._internal_get_friends(
                friendsOffset, friends_max_length, False)
            for item in apiRes:
                friends_map[item["id"]] = FriendInfo(
                    item["id"], item["username"], item["displayName"], None, update_time)
            friendsOffset += len(apiRes)

            if len(apiRes) != friends_max_length:
                break

        # 取得 (オフライン)
        friendsOffset = 0
        while True:
            apiRes = self._internal_get_friends(
                friendsOffset, friends_max_length, True)
            for item in apiRes:
                friends_map[item["id"]] = FriendInfo(
                    item["id"], item["username"], item["displayName"], None, update_time)
            friendsOffset += len(apiRes)

            if len(apiRes) != friends_max_length:
                break

        # フレンド一覧 (表示名付き) を作成
        friend_infos = [
            friends_map[user_id] or FriendInfo(user_id, None, None, None, None)
            for user_id in friend_ids
        ]
        return friend_infos

    def _internal_get_current_user(self, headers):
        target_url = f"{VRChatResource.ENDPOINT_URL}/auth/user"
        req = request.Request(target_url, method="GET", headers=headers)
        res = self._opener.open(req)
        dat = json.load(res)
        return dat

    def _internal_get_friends(self, offset: int = 0, n: int = 50, offline: bool = False):
        query = parse.urlencode({
            "offline": "true" if offline else "false",
            "n": n,
            "offset": offset,
            "apiKey": VRChatResource.APIKEY
        })
        target_url = f"{VRChatResource.ENDPOINT_URL}/auth/user/friends?{query}"
        req = request.Request(target_url, method="GET")
        res = self._opener.open(req)
        dat = json.load(res)
        return dat


class DbResource:
    dynamodb = boto3.client("dynamodb")
    dynamodb_res = boto3.resource("dynamodb")

    def __init__(self, current_user_id: str, get_table_name: str, put_table_name: str):
        self._current_user_id = current_user_id
        self._get_table = DbResource.dynamodb_res.Table(get_table_name)
        self._put_table = DbResource.dynamodb_res.Table(put_table_name)

    def get_account(self) -> tuple[str, str, MozillaCookieJar]:
        res_api = self._get_table.get_item(Key={
            "pk": "#app:monitoring_accounts",
            "sk": f"#account:{self._current_user_id}"
        })
        res_api = res_api["Item"]
        user_name = res_api["user_name"]
        passwd = res_api["passwd"]
        cookies = DbResource.text2cookiejar(res_api["cookies"]) \
            if "cookies" in res_api else MozillaCookieJar()

        return user_name, passwd, cookies

    def put_account(self, user_name: str = None, passwd: str = None, cookies: MozillaCookieJar = None, update_date: datetime.datetime = None) -> None:
        update_unixtime = int(update_date.timestamp()) if update_date is not None else None
        cookies_txt = DbResource.cookiejar2text(cookies) if cookies is not None else None

        # 更新式を作成
        exp_update = "SET "
        exp_base = {
            "user_name": user_name,
            "passwd": passwd,
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
                "sk": f"#account:{self._current_user_id}"
            },
            UpdateExpression=exp_update,
            ExpressionAttributeValues=exp_values
        )

    def get_friends(self) -> list[FriendInfo]:
        db_res = self._get_table.query(
            KeyConditionExpression="pk = :pk and begins_with(sk, :sk)",
            ExpressionAttributeValues={
                ":pk": f"#account:{self._current_user_id}",
                ":sk": "#friend:"
            }
        )
        friend_infos = [
            FriendInfo(
                item["user_id"], item["user_name"], item["user_display_name"],
                item.get("regist_date"), item["update_date"]) for item in db_res["Items"]
        ]
        return friend_infos

    def put_friend(self, opInfo: OperationInfo) -> None:
        # 失敗した場合には再試行。2回失敗した場合は catch 句で中断させる
        for i in range(2):
            try:
                if opInfo.action_type == ActionType.Add:
                    self._put_table.put_item(
                        Item={
                            "pk": f"#account:{self._current_user_id}",
                            "sk": f"#friend:{opInfo.info_new.user_id}",
                            "user_id": opInfo.info_new.user_id,
                            "user_name": opInfo.info_new.user_name,
                            "user_display_name": opInfo.info_new.user_display_name,
                            "regist_date": opInfo.info_new.update_date,
                            "update_date": opInfo.info_new.update_date
                        }
                    )
                elif (opInfo.action_type == ActionType.Update):
                    self._put_table.put_item(
                        Item={
                            "pk": f"#account:{self._current_user_id}",
                            "sk": f"#friend:{opInfo.info_new.user_id}",
                            "user_id": opInfo.info_new.user_id,
                            "user_name": opInfo.info_new.user_name,
                            "user_display_name": opInfo.info_new.user_display_name,
                            "regist_date": opInfo.info_old.regist_date,
                            "update_date": opInfo.info_new.update_date
                        }
                    )
                elif (opInfo.action_type == ActionType.Remove):
                    self._put_table.delete_item(
                        Key={
                            "pk": f"#account:{self._current_user_id}",
                            "sk": f"#friend:{opInfo.info_old.user_id}"
                        }
                    )
                else:
                    raise Exception("想定外のエラーが発生しました")

                time.sleep(0.1)
                break
            except DbResource.dynamodb.exceptions.ProvisionedThroughputExceededException as ex:
                time.sleep(10)
                logger.warning("キャパシティ超過")

    @ staticmethod
    def text2cookiejar(text: str) -> CookieJar:
        cookie_jar = MozillaCookieJar()
        if text != None:
            with tempfile.NamedTemporaryFile("w") as tmp:
                tmp.write(text)
                tmp.file.flush()
                cookie_jar.load(tmp.name)
        return cookie_jar

    @ staticmethod
    def cookiejar2text(cookies: MozillaCookieJar) -> str:
        with tempfile.NamedTemporaryFile("r") as tmp:
            cookies.save(tmp.name)
            return tmp.read()


class App:
    def __init__(self, user_name: str, passwd: str, processer_put_queue: str, vrc: VRChatResource, db: DbResource):
        self._user_name = user_name
        self._passwd = passwd
        self._processer_put_queue = processer_put_queue
        self._vrc = vrc
        self._db = db

    def invoke(self, update_date: datetime.datetime):
        current_user_info = self._vrc.get_current_user(self._user_name, self._passwd)
        friends_in_vrc = self._vrc.get_friends(current_user_info, update_date)
        friends_in_db = self._db.get_friends()

        ops = list(self.extract_change_friends(friends_in_db, friends_in_vrc))
        for item in ops:
            job_json = json.dumps(
                {"account_id": current_user_info["id"], "event": item}, ensure_ascii=False, cls=CustomJsonEncoder)
            sqs = boto3.resource("sqs")
            vfe_queue = sqs.get_queue_by_name(
                QueueName=self._processer_put_queue)
            vfe_queue.send_message(
                MessageBody=job_json,
                MessageAttributes={
                    "Type": {"DataType": "String", "StringValue": "InvokeFunction"}
                }
            )
            self._db.put_friend(item)

    def extract_change_friends(self, friends_in_db: list[FriendInfo], friends_in_vrc: list[FriendInfo]) -> typing.Iterable[OperationInfo]:
        i_dbside, i_vrcside = 0, 0
        while i_dbside < len(friends_in_db) or i_vrcside < len(friends_in_vrc):
            friend_in_db: FriendInfo = None
            friendid_in_db = "zzz"
            if i_dbside < len(friends_in_db):
                friend_in_db = friends_in_db[i_dbside]
                friendid_in_db = friend_in_db.user_id

            friend_in_vrc: FriendInfo = None
            friend_id_in_vrc = "000"
            if i_vrcside < len(friends_in_vrc):
                friend_in_vrc = friends_in_vrc[i_vrcside]
                friend_id_in_vrc = friend_in_vrc.user_id

            # 更新を抽出
            if friendid_in_db == friend_id_in_vrc:
                if not App._internal_equalsFriendInfo(friend_in_db, friend_in_vrc):
                    yield OperationInfo(ActionType.Update, friend_in_vrc, friend_in_db)
                i_dbside += 1
                i_vrcside += 1
            # 削除を抽出
            elif friendid_in_db < friend_id_in_vrc:
                yield OperationInfo(ActionType.Remove, None, friend_in_db)
                i_dbside += 1
            # 追加を抽出
            else:
                yield OperationInfo(ActionType.Add, friend_in_vrc, None)
                i_vrcside += 1

    @staticmethod
    def _internal_equalsFriendInfo(value1: FriendInfo, value2: FriendInfo):
        return value1.user_id == value2.user_id \
            and value1.user_name == value2.user_name \
            and value1.user_display_name == value2.user_display_name


def lambda_handler(event, context):
    APP_GET_TABLE_NAME = os.getenv("APP_GET_TABLE_NAME")
    APP_PUT_TABLE_NAME = os.getenv("APP_PUT_TABLE_NAME")
    PROCESSER_PUT_QUEUE = os.getenv("PROCESSER_PUT_QUEUE")

    for job in event["Records"]:
        # キューイングされた情報を取得
        job_info = json.loads(job["body"])
        user_id = job_info["user_id"]

        # 前回処理時の認証情報が有れば取得
        res_db = DbResource(user_id, APP_GET_TABLE_NAME, APP_PUT_TABLE_NAME)
        user_name, passwd, cookies = res_db.get_account()

        # 本処理
        update_date = datetime.datetime.now()
        res_vrc = VRChatResource(cookies)
        app = App(user_name, passwd, PROCESSER_PUT_QUEUE, res_vrc, res_db)
        app.invoke(update_date)

        # 後始末
        res_db.put_account(cookies=cookies, update_date=update_date)
