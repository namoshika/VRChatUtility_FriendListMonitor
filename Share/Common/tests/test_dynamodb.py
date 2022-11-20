import datetime
import logging
import os
import sys
import boto3


class TestService:
    def test_crud_account(self):
        sys.path.append("src")
        import src.dynamodb

        logger = logging.getLogger(__name__)
        store = src.dynamodb.Service(
            "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            os.getenv("APP_GET_TABLE_NAME"),
            os.getenv("APP_PUT_TABLE_NAME"),
            boto3.Session(),
            logger
        )

        # アカウント一覧を取得
        accounts = list(src.dynamodb.Service.get_accounts(
            os.getenv("APP_GET_TABLE_NAME"), datetime.datetime.now(), 0, 10))
        assert len(accounts) > 0

        # アカウント情報を登録
        put_info = src.dynamodb.AccountInfo("ユーザ名", "パスワード", None)
        store.put_account(put_info, datetime.datetime.now())

        # アカウント情報を取得
        get_info = store.get_account()
        assert get_info.vrchat_user_name == put_info.vrchat_user_name
        assert get_info.vrchat_passwd == put_info.vrchat_passwd
        assert get_info.cookies is not None

        # アカウント情報を削除
        store.del_account()

    def test_crud_app(self):
        sys.path.append("src")
        import src.dynamodb

        logger = logging.getLogger(__name__)
        store = src.dynamodb.Service(
            "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            os.getenv("APP_GET_TABLE_NAME"),
            os.getenv("APP_PUT_TABLE_NAME"),
            boto3.Session(),
            logger
        )

        res = store.get_app_metadata("sample_app")
        assert res is None

        store.connect_app("sample_app", {"key1": "val1", "key2": "val2"})
        res = store.get_app_metadata("sample_app")
        assert res["key1"] == "val1" and res["key2"] == "val2"

        store.disconnect_app("sample_app")
        res = store.get_app_metadata("sample_app")
        assert res is None

    def test_crud_friend(self):
        sys.path.append("src")
        import src.dynamodb

        logger = logging.getLogger(__name__)
        store = src.dynamodb.Service(
            "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            os.getenv("APP_GET_TABLE_NAME"),
            os.getenv("APP_PUT_TABLE_NAME"),
            boto3.Session(),
            logger
        )

        # フレンド情報を登録
        friend_info_1a = src.dynamodb.FriendInfo("ユーザID1", "ユーザ名1", "ユーザ表示名1", 0, 0)
        op = src.dynamodb.OperationInfo(src.dynamodb.ActionType.ADD, friend_info_1a, None)
        store.put_friend(op)

        friend_info_2a = src.dynamodb.FriendInfo("ユーザID2", "ユーザ名2", "ユーザ表示名2", 0, 0)
        op = src.dynamodb.OperationInfo(src.dynamodb.ActionType.ADD, friend_info_2a, None)
        store.put_friend(op)

        friend_info_3a = src.dynamodb.FriendInfo("ユーザID3", "ユーザ名3", "ユーザ表示名3", 0, 0)
        op = src.dynamodb.OperationInfo(src.dynamodb.ActionType.ADD, friend_info_3a, None)
        store.put_friend(op)

        # フレンド情報を取得
        res = store.get_friends()
        assert len(res) == 3

        assert res[0].user_id == friend_info_1a.user_id
        assert res[0].user_name == friend_info_1a.user_name
        assert res[0].user_display_name == friend_info_1a.user_display_name
        assert res[0].regist_date == friend_info_1a.regist_date
        assert res[0].update_date == friend_info_1a.update_date

        assert res[1].user_id == friend_info_2a.user_id
        assert res[1].user_name == friend_info_2a.user_name
        assert res[1].user_display_name == friend_info_2a.user_display_name
        assert res[1].regist_date == friend_info_2a.regist_date
        assert res[1].update_date == friend_info_2a.update_date

        assert res[2].user_id == friend_info_3a.user_id
        assert res[2].user_name == friend_info_3a.user_name
        assert res[2].user_display_name == friend_info_3a.user_display_name
        assert res[2].regist_date == friend_info_3a.regist_date
        assert res[2].update_date == friend_info_3a.update_date

        # フレンド情報を更新
        friend_info_1b = src.dynamodb.FriendInfo("ユーザID1", "ユーザ名1 (更新後)", "ユーザ表示名1 (更新後)", 0, 0)
        op = src.dynamodb.OperationInfo(src.dynamodb.ActionType.UPDATE, friend_info_1b, friend_info_1a)
        store.put_friend(op)

        res = store.get_friends()
        assert len(res) == 3

        assert res[0].user_id == friend_info_1b.user_id
        assert res[0].user_name == friend_info_1b.user_name
        assert res[0].user_display_name == friend_info_1b.user_display_name
        assert res[0].regist_date == friend_info_1b.regist_date
        assert res[0].update_date == friend_info_1b.update_date

        assert res[1].user_id == friend_info_2a.user_id
        assert res[1].user_name == friend_info_2a.user_name
        assert res[1].user_display_name == friend_info_2a.user_display_name
        assert res[1].regist_date == friend_info_2a.regist_date
        assert res[1].update_date == friend_info_2a.update_date

        assert res[2].user_id == friend_info_3a.user_id
        assert res[2].user_name == friend_info_3a.user_name
        assert res[2].user_display_name == friend_info_3a.user_display_name
        assert res[2].regist_date == friend_info_3a.regist_date
        assert res[2].update_date == friend_info_3a.update_date

        # フレンド情報を削除
        op = src.dynamodb.OperationInfo(src.dynamodb.ActionType.REMOVE, None, friend_info_1a)
        store.put_friend(op)
        op = src.dynamodb.OperationInfo(src.dynamodb.ActionType.REMOVE, None, friend_info_2a)
        store.put_friend(op)
        op = src.dynamodb.OperationInfo(src.dynamodb.ActionType.REMOVE, None, friend_info_3a)
        store.put_friend(op)

    def test_crud_activity(self):
        sys.path.append("src")
        import src.dynamodb

        logger = logging.getLogger(__name__)
        store = src.dynamodb.Service(
            "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
            os.getenv("APP_GET_TABLE_NAME"),
            os.getenv("APP_PUT_TABLE_NAME"),
            boto3.Session(),
            logger
        )

        # アクティビティを登録
        log_type_1 = src.dynamodb.LogEventType.ENTER_WORLD
        log_time_1 = datetime.datetime(2012, 1, 23, 1, 23, 45)
        log_item_1 = src.dynamodb.LogEventEnterWorld(log_type_1, log_time_1, "inst_id", "wrld_id", "ワールド名")
        store.put_activity(log_item_1)

        log_type_2 = src.dynamodb.LogEventType.LEFT_WORLD
        log_time_2 = datetime.datetime(2012, 1, 23, 1, 23, 45)
        log_item_2 = src.dynamodb.LogEventLeftWorld(log_type_2, log_time_2, "inst_id", "wrld_id", "ワールド名")
        store.put_activity(log_item_2)

        # 始端境界値 (外)
        log_type_3 = src.dynamodb.LogEventType.ENTER_PLAYER
        log_time_3 = datetime.datetime(2012, 1, 22, 19, 24, 44)
        log_item_3 = src.dynamodb.LogEventEnterPlayer(log_type_3, log_time_3, "inst_id_1", "wrld_id_1", "ワールド名_1", "ユーザ表示名")
        store.put_activity(log_item_3)

        # 始端境界値 (内)
        log_type_4 = src.dynamodb.LogEventType.ENTER_PLAYER
        log_time_4 = datetime.datetime(2012, 1, 22, 19, 24, 45)
        log_item_4 = src.dynamodb.LogEventEnterPlayer(log_type_4, log_time_4, "inst_id_2", "wrld_id_2", "ワールド名_2", "ユーザ表示名")
        store.put_activity(log_item_4)

        # 終端境界値 (内)
        log_type_5 = src.dynamodb.LogEventType.ENTER_PLAYER
        log_time_5 = datetime.datetime(2012, 1, 23, 1, 24, 45)
        log_item_5 = src.dynamodb.LogEventEnterPlayer(log_type_5, log_time_5, "inst_id_3", "wrld_id_3", "ワールド名_3", "ユーザ表示名")
        store.put_activity(log_item_5)

        log_type_6 = src.dynamodb.LogEventType.ENTER_PLAYER
        log_time_6 = datetime.datetime(2012, 1, 23, 1, 25, 45)
        log_item_6 = src.dynamodb.LogEventEnterPlayer(log_type_6, log_time_6, "inst_id_4", "wrld_id_4", "ワールド名_4", "ユーザ表示名")
        store.put_activity(log_item_6)

        log_type_7 = src.dynamodb.LogEventType.LEFT_PLAYER
        log_time_7 = datetime.datetime(2012, 1, 23, 1, 23, 45)
        log_item_7 = src.dynamodb.LogEventLeftPlayer(log_type_7, log_time_7, "inst_id_5", "wrld_id_5", "ワールド名_5", "ユーザ表示名")
        store.put_activity(log_item_7)

        # アクティビティを検索
        friend_info = src.dynamodb.FriendInfo("ユーザ名", "ユーザ名", "ユーザ表示名", 0, 0)
        max_datetime = datetime.datetime(2012, 1, 23, 1, 24, 45)
        activity = store.find_first_activity(friend_info, max_datetime)
        assert activity.type == src.dynamodb.LogEventType.ENTER_PLAYER
        assert activity.instance_id == "inst_id_2"
        assert activity.world_id == "wrld_id_2"
        assert activity.world_name == "ワールド名_2"
        assert activity.user_display_name == "ユーザ表示名"
        assert activity.timestamp == log_time_4.astimezone()
