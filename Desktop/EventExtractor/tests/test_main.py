import boto3
import datetime
import json
import logging
import sys
import os
import shutil
import pytest
from pathlib import Path

sys.path.append("src")


class TestVRChatResource:
    def test_readLog(self):
        from src import main
        log_dir = Path("tests/data/log")
        target = main.VRChatResource(log_dir)
        reader = target.read_log(
            "認証ユーザ1",
            {
                "output_log_sample01.txt": main.entity.LogParserStatus(0, 0, None, None, None, None),
                "output_log_sample02.txt": main.entity.LogParserStatus(0, 0, None, None, None, None),
                "output_log_sample03.txt": main.entity.LogParserStatus(0, 0, None, None, None, None),
            }
        )
        logs = list(reader)
        assert len(logs) > 0


class TestVRChatLogReader:
    def test_read(self):
        from src import main
        # 対象ユーザ (最初から)
        status = main.entity.LogParserStatus(0, 0, None, None, None, None)
        reader = main.VRChatLogReader(
            Path("tests/data/log/output_log_sample01.txt"), True, "認証ユーザ1", status)

        logs = list(reader.read())
        assert len(logs) == 5

        # 非対象ユーザ (最初から Case01)
        status = main.entity.LogParserStatus(0, 0, None, None, None, None)
        reader = main.VRChatLogReader(
            Path("tests/data/log/output_log_sample01.txt"), True, "認証ユーザ2", status)
        logs = list(reader.read())

        # 非対象ユーザ (最初から Case02)
        status = main.entity.LogParserStatus(0, 0, None, None, None, None)
        reader = main.VRChatLogReader(
            Path("tests/data/log_err/output_log_err01.txt"), True, "認証ユーザ1", status)
        logs = list(reader.read())

        # 対象ユーザ (途中から)
        status = main.entity.LogParserStatus(0, 0, None, None, None, None)
        reader = main.VRChatLogReader(
            Path("tests/data/log/output_log_sample01.txt"), True, "認証ユーザ1", status)

        iterator = iter(reader.read())
        obj = next(iterator)
        obj = next(iterator)

        reader = main.VRChatLogReader(
            Path("tests/data/log/output_log_sample01.txt"), True, "認証ユーザ1", reader._status)
        obj = list(reader.read())
        assert len(obj) == 3

    def test_read_log(self):
        from src import main
        status = main.entity.LogParserStatus(0, 0, "認証ユーザ1", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        buff = open("tests/data/log/output_log_sample01.txt", "r")
        res = main.VRChatLogReader.read_log(buff, True, "認証ユーザ1", status)
        res = list(res)
        assert len(res) > 0

    def test_proc_logevent_text_EnterRoom(self):
        from src import main
        status = main.entity.LogParserStatus(
            0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")

        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Entering Room: ワールド名\n\n\n", "認証ユーザ", status)
        assert res is None
        assert status.authuser_display_name == "認証ユーザ"
        assert status.current_instance_id is None
        assert status.current_world_id is None
        assert status.current_world_name == "ワールド名"
        assert status.visited_world_count == 0

        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Joining wrld_ffffffff-ffff-ffff-ffff-ffffffffffff:99999~private(usr_ffffffff-ffff-ffff-ffff-ffffffffffff)~region(jp)~nonce(XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX)\n\n\n", "認証ユーザ", status)
        assert res.type == main.entity.LogEventType.JOIN_INSTANCE
        assert status.authuser_display_name == "認証ユーザ"
        assert status.current_instance_id == "99999~private(usr_ffffffff-ffff-ffff-ffff-ffffffffffff)~region(jp)~nonce(XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX)"
        assert status.current_world_id == "wrld_ffffffff-ffff-ffff-ffff-ffffffffffff"
        assert status.current_world_name == "ワールド名"
        assert status.visited_world_count == 1

    def test_proc_logevent_text_EnterPlayer(self):
        from src import main
        status = main.entity.LogParserStatus(
            0, 0, "認証ユーザ", "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerJoined ユーザ名\n\n\n", "認証ユーザ", status)

        assert res.type == main.entity.LogEventType.ENTER_PLAYER
        assert status.authuser_display_name == "認証ユーザ"
        assert status.current_instance_id == "初期インスタンスID"
        assert status.current_world_id == "初期ワールドID"
        assert status.current_world_name == "初期ワールド名"
        assert status.visited_world_count == 0

        status = main.entity.LogParserStatus(0, 0, "認証ユーザ", None, None, None)
        with pytest.raises(main.entity.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerJoined ユーザ名\n\n\n", "認証ユーザ", status)
        assert ex.value.reason == main.entity.VRChatLogErrorType.INVALID_STATUS

    def test_proc_logevent_text_LeftWorld(self):
        from src import main
        status = main.entity.LogParserStatus(
            0, 0, "認証ユーザ", "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnLeftRoom\n\n\n", "認証ユーザ", status)

        assert res.type == main.entity.LogEventType.LEFT_WORLD
        assert status.authuser_display_name == "認証ユーザ"
        assert status.current_instance_id == "初期インスタンスID"
        assert status.current_world_id == "初期ワールドID"
        assert status.current_world_name == "初期ワールド名"
        assert status.visited_world_count == 0

        status = main.entity.LogParserStatus(0, 0, "認証ユーザ", None, None, None)
        with pytest.raises(main.entity.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] OnLeftRoom\n\n\n", "認証ユーザ", status)
        assert ex.value.reason == main.entity.VRChatLogErrorType.INVALID_STATUS

    def test_proc_logevent_text_LeftPlayer(self):
        from src import main
        status = main.entity.LogParserStatus(
            0, 0, "認証ユーザ", "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerLeft ユーザ名\n\n\n", "認証ユーザ", status)

        assert res.type == main.entity.LogEventType.LEFT_PLAYER
        assert status.authuser_display_name == "認証ユーザ"
        assert status.current_instance_id == "初期インスタンスID"
        assert status.current_world_id == "初期ワールドID"
        assert status.current_world_name == "初期ワールド名"
        assert status.visited_world_count == 0

        status = main.entity.LogParserStatus(0, 0, "認証ユーザ", None, None, None)
        with pytest.raises(main.entity.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerLeft ユーザ名\n\n\n", "認証ユーザ", status)

    def test_proc_logevent_text_InitializedApi(self):
        from src import main
        status = main.entity.LogParserStatus(
            0, 1, None, "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Initialized PlayerAPI \"認証ユーザ1\" is local\n\n\n", "認証ユーザ1", status)

        assert res.type == main.entity.LogEventType.INITIALIZE_API
        assert status.authuser_display_name == "認証ユーザ1"
        assert status.current_instance_id == "初期インスタンスID"
        assert status.current_world_id == "初期ワールドID"
        assert status.current_world_name == "初期ワールド名"
        assert status.visited_world_count == 1

        status = main.entity.LogParserStatus(
            0, 1, None, "初期ワールドID", "初期ワールド名", "初期インスタンスID")

        with pytest.raises(main.entity.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] Initialized PlayerAPI \"認証ユーザ1\" is local\n\n\n", "認証ユーザ2", status)
        assert ex.value.reason == main.entity.VRChatLogErrorType.MISS_MATCH_AUTHUSER

        status = main.entity.LogParserStatus(
            0, 2, None, "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        with pytest.raises(main.entity.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] Initialized PlayerAPI \"認証ユーザ1\" is local\n\n\n", "認証ユーザ1", status)
        assert ex.value.reason == main.entity.VRChatLogErrorType.INVALID_STATUS

    def test_parse_activity(self):
        from src import main
        status = main.entity.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Entering Room: ワールド名\n\n\n", status
        )
        assert res.type == main.entity.LogEventType.ENTER_WORLD
        assert res.timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.instance_id == "現在インスタンスID"
        assert res.world_id == "現在ワールドID"
        assert res.world_name == "ワールド名"

        status = main.entity.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnLeftRoom\n\n\n", status
        )
        assert res.type == main.entity.LogEventType.LEFT_WORLD
        assert res.timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.instance_id == "現在インスタンスID"
        assert res.world_id == "現在ワールドID"
        assert res.world_name == "現在ワールド名"

        status = main.entity.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerJoined ユーザ名\n\n\n", status
        )
        assert res.type == main.entity.LogEventType.ENTER_PLAYER
        assert res.timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.instance_id == "現在インスタンスID"
        assert res.world_id == "現在ワールドID"
        assert res.world_name == "現在ワールド名"
        assert res.user_display_name == "ユーザ名"

        status = main.entity.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Initialized PlayerAPI \"ユーザ名\"hogehoge\" is local", status
        )
        assert res.type == main.entity.LogEventType.INITIALIZE_API
        assert res.timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.instance_id == "現在インスタンスID"
        assert res.world_id == "現在ワールドID"
        assert res.world_name == "現在ワールド名"
        assert res.user_display_name == "ユーザ名\"hogehoge"
        assert res.mode == "local"

        status = main.entity.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerLeft ユーザ名\n\n\n", status
        )
        assert res.type == main.entity.LogEventType.LEFT_PLAYER
        assert res.timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.instance_id == "現在インスタンスID"
        assert res.world_id == "現在ワールドID"
        assert res.world_name == "現在ワールド名"
        assert res.user_display_name == "ユーザ名"


class TestApp:
    def setup(self):
        pth = Path("tests/sandbox/checkpoint")
        shutil.rmtree(pth, ignore_errors=True)
        pth.mkdir(parents=True, exist_ok=True)

    def test_invoke(self):
        from src import main
        from src.common import dynamodb

        app_get_dir = Path("./tests/data").resolve()
        app_put_dir = Path("./tests/sandbox").resolve()
        app = main.App(app_get_dir, app_put_dir, "sample")
        vrc = main.VRChatResource(app.log_dir)
        dyn = dynamodb.Service(
            app.account_id,
            os.getenv("APP_GET_TABLE_NAME"),
            os.getenv("APP_PUT_TABLE_NAME"),
            boto3.Session(), logging.getLogger()
        )
        app.init(vrc, dyn)
        app.invoke()

    def test_get_status(self):
        from src import main
        status = main.App.get_status(Path("tests/data"), "sample")
        assert len(status) == 3

        obj = status["log_01.txt"]
        assert obj.authuser_display_name == "hoge"
        assert obj.current_instance_id == "99999"
        assert obj.current_world_id == "wrld_xxx"
        assert obj.current_world_name == "ワールド名"
        assert obj.pos == 123
        assert obj.visited_world_count == 1

        obj = status["log_02.txt"]
        assert obj.authuser_display_name == "hoge"
        assert obj.current_instance_id == "99999"
        assert obj.current_world_id == "wrld_xxx"
        assert obj.current_world_name == "ワールド名"
        assert obj.pos == 123
        assert obj.visited_world_count == 1

        obj = status["log_03.txt"]
        assert obj.authuser_display_name == "hoge"
        assert obj.current_instance_id == "99999"
        assert obj.current_world_id == "wrld_xxx"
        assert obj.current_world_name == "ワールド名"
        assert obj.pos == 123
        assert obj.visited_world_count == 1

    def test_set_status(self):
        from src import main
        main.App.set_status(Path("tests/sandbox"), "sample", {
            "log_01.txt": main.entity.LogParserStatus(123, 0, "認証ユーザ", "ワールドID1", "ワールド名1", "インスタンスID1"),
            "log_02.txt": main.entity.LogParserStatus(234, 0, "認証ユーザ", "ワールドID2", "ワールド名2", "インスタンスID2"),
            "log_03.txt": main.entity.LogParserStatus(345, 0, "認証ユーザ", "ワールドID3", "ワールド名3", "インスタンスID3"),
        })

        with open("tests/sandbox/checkpoint/sample.json", mode="r", encoding="utf8") as f:
            status = json.load(f)
            assert len(status) == 3

            obj = status["log_01.txt"]
            assert obj["_type"] == "LogParserStatus"
            assert obj["AuthUserDisplayName"] == "認証ユーザ"
            assert obj["CurrentInstanceId"] == "インスタンスID1"
            assert obj["CurrentWorldId"] == "ワールドID1"
            assert obj["CurrentWorldName"] == "ワールド名1"
            assert obj["Pos"] == 123
            assert obj["VisitedWorldCount"] == 0

            obj = status["log_02.txt"]
            assert obj["_type"] == "LogParserStatus"
            assert obj["AuthUserDisplayName"] == "認証ユーザ"
            assert obj["CurrentInstanceId"] == "インスタンスID2"
            assert obj["CurrentWorldId"] == "ワールドID2"
            assert obj["CurrentWorldName"] == "ワールド名2"
            assert obj["Pos"] == 234
            assert obj["VisitedWorldCount"] == 0

            obj = status["log_03.txt"]
            assert obj["_type"] == "LogParserStatus"
            assert obj["AuthUserDisplayName"] == "認証ユーザ"
            assert obj["CurrentInstanceId"] == "インスタンスID3"
            assert obj["CurrentWorldId"] == "ワールドID3"
            assert obj["CurrentWorldName"] == "ワールド名3"
            assert obj["Pos"] == 345
            assert obj["VisitedWorldCount"] == 0
