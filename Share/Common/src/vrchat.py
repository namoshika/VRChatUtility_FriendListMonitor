import base64
import json
from datetime import datetime
from http.cookiejar import CookieJar
from urllib import request, parse, error
from .entity import *


class Service:
    ENDPOINT_URL = "https://api.vrchat.cloud/api/1"
    APIKEY = "JlE5Jldo5Jibnk5O5hTx6XVqsJu4WJ26"

    def __init__(self, vrc_username: str, vrc_passwd: str, cookie_jar: CookieJar) -> None:
        self._vrc_username = vrc_username
        self._vrc_passwd = vrc_passwd
        opener = request.build_opener(request.HTTPCookieProcessor(cookie_jar))
        opener.addheaders = [
            ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/103.0.0.0 Safari/537.36"),
            ("Accept", "application/json")
        ]
        self._opener = opener

    def get_current_user(self) -> dict:
        headers: dict[str, str] = dict()
        for i in range(2):
            try:
                api_res = self._internal_get_current_user(headers)
                return api_res
            except error.HTTPError as e:
                if (i == 0 and e.status == 401):
                    headers["Authorization"] = "Basic " + base64.b64encode(
                        f"{self._vrc_username}:{self._vrc_passwd}".encode("utf8")).decode("utf8")
                else:
                    raise

    def get_friends(self, current_user_info, update_time: datetime) -> list[UserInfo]:
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
                friends_map[item["id"]] = UserInfo(
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
                friends_map[item["id"]] = UserInfo(
                    item["id"], item["username"], item["displayName"], None, update_time)
            friendsOffset += len(apiRes)

            if len(apiRes) != friends_max_length:
                break

        # フレンド一覧 (表示名付き) を作成
        friend_infos = [
            friends_map[user_id] or UserInfo(user_id, None, None, None, None)
            for user_id in friend_ids
        ]
        return friend_infos

    def _internal_get_current_user(self, headers):
        target_url = f"{self.ENDPOINT_URL}/auth/user"
        req = request.Request(target_url, method="GET", headers=headers)
        res = self._opener.open(req)
        dat = json.load(res)
        return dat

    def _internal_get_friends(self, offset: int = 0, n: int = 50, offline: bool = False):
        query = parse.urlencode({
            "offline": "true" if offline else "false",
            "n": n,
            "offset": offset,
            "apiKey": self.APIKEY
        })
        target_url = f"{self.ENDPOINT_URL}/auth/user/friends?{query}"
        req = request.Request(target_url, method="GET")
        res = self._opener.open(req)
        dat = json.load(res)
        return dat
