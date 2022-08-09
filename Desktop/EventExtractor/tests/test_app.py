import datetime
import json
import os
import shutil
import pytest
from src import main
from pathlib import Path

import boto3

class TestVRChatResource:
    def test_readLog(self):
        log_dir = Path("tests/data/log")
        target = main.VRChatResource(log_dir)
        reader = target.read_log(
            "認証ユーザ1",
            {
                "output_log_sample01.txt": main.LogParserStatus(0, 0, None, None, None, None),
                "output_log_sample02.txt": main.LogParserStatus(0, 0, None, None, None, None),
                "output_log_sample03.txt": main.LogParserStatus(0, 0, None, None, None, None),
            }
        )
        for item in reader:
            pass


class TestVRChatLogReader:
    def test_read(self):
        # 対象ユーザ (最初から)
        status = main.LogParserStatus(0, 0, None, None, None, None)
        reader = main.VRChatLogReader(
            Path("tests/data/log/output_log_sample01.txt"), True, "認証ユーザ1", status)

        logs = list(reader.read())
        assert len(logs) == 5

        # 非対象ユーザ (最初から Case01)
        status = main.LogParserStatus(0, 0, None, None, None, None)
        reader = main.VRChatLogReader(
            Path("tests/data/log/output_log_sample01.txt"), True, "認証ユーザ2", status)
        logs = list(reader.read())

        # 非対象ユーザ (最初から Case02)
        status = main.LogParserStatus(0, 0, None, None, None, None)
        reader = main.VRChatLogReader(
            Path("tests/data/log_err/output_log_err01.txt"), True, "認証ユーザ1", status)

        with pytest.raises(main.VRChatLogError) as ex:
            logs = list(reader.read())
        assert ex.value.reason == main.VRChatLogErrorType.LogBufferOverflow
        
        # 対象ユーザ (途中から)
        status = main.LogParserStatus(0, 0, None, None, None, None)
        reader = main.VRChatLogReader(
            Path("tests/data/log/output_log_sample01.txt"), True, "認証ユーザ1", status)

        iterator = iter(reader.read())
        obj = next(iterator)
        obj = next(iterator)

        reader = main.VRChatLogReader(
            Path("tests/data/log/output_log_sample01.txt"), True, "認証ユーザ1", status)
        obj = list(reader.read())
        assert len(obj) == 3

    def test_read_log(self):
        status = main.LogParserStatus(0, 0, "認証ユーザ1", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        buff = open("tests/data/log/output_log_sample01.txt", "r")
        res = main.VRChatLogReader.read_log(buff, True, "認証ユーザ1", 0, status)

        for item in res:
            pass

    def test_proc_logevent_text_EnterRoom(self):
        status = main.LogParserStatus(
            0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")

        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Entering Room: ワールド名\n\n\n", "認証ユーザ", status)
        assert res is None
        assert status.AuthUserDisplayName == "認証ユーザ"
        assert status.CurrentInstanceId is None
        assert status.CurrentWorldId is None
        assert status.CurrentWorldName == "ワールド名"
        assert status.VisitedWorldCount == 0

        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Joining wrld_ffffffff-ffff-ffff-ffff-ffffffffffff:99999~private(usr_ffffffff-ffff-ffff-ffff-ffffffffffff)~region(jp)~nonce(XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX)\n\n\n", "認証ユーザ", status)
        assert res.Type == main.LogEventType.JoiningInstance
        assert status.AuthUserDisplayName == "認証ユーザ"
        assert status.CurrentInstanceId == "99999~private(usr_ffffffff-ffff-ffff-ffff-ffffffffffff)~region(jp)~nonce(XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX)"
        assert status.CurrentWorldId == "wrld_ffffffff-ffff-ffff-ffff-ffffffffffff"
        assert status.CurrentWorldName == "ワールド名"
        assert status.VisitedWorldCount == 1

    def test_proc_logevent_text_EnterPlayer(self):
        status = main.LogParserStatus(
            0, 0, "認証ユーザ", "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerJoined ユーザ名\n\n\n", "認証ユーザ", status)

        assert res.Type == main.LogEventType.EnterPlayer
        assert status.AuthUserDisplayName == "認証ユーザ"
        assert status.CurrentInstanceId == "初期インスタンスID"
        assert status.CurrentWorldId == "初期ワールドID"
        assert status.CurrentWorldName == "初期ワールド名"
        assert status.VisitedWorldCount == 0

        status = main.LogParserStatus(0, 0, "認証ユーザ", None, None, None)
        with pytest.raises(main.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerJoined ユーザ名\n\n\n", "認証ユーザ", status)
        assert ex.value.reason == main.VRChatLogErrorType.InvalidStatus

    def test_proc_logevent_text_LeftWorld(self):
        status = main.LogParserStatus(
            0, 0, "認証ユーザ", "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnLeftRoom\n\n\n", "認証ユーザ", status)

        assert res.Type == main.LogEventType.LeftWorld
        assert status.AuthUserDisplayName == "認証ユーザ"
        assert status.CurrentInstanceId == "初期インスタンスID"
        assert status.CurrentWorldId == "初期ワールドID"
        assert status.CurrentWorldName == "初期ワールド名"
        assert status.VisitedWorldCount == 0

        status = main.LogParserStatus(0, 0, "認証ユーザ", None, None, None)
        with pytest.raises(main.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] OnLeftRoom\n\n\n", "認証ユーザ", status)
        assert ex.value.reason == main.VRChatLogErrorType.InvalidStatus

    def test_proc_logevent_text_LeftPlayer(self):
        status = main.LogParserStatus(
            0, 0, "認証ユーザ", "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerLeft ユーザ名\n\n\n", "認証ユーザ", status)

        assert res.Type == main.LogEventType.LeftPlayer
        assert status.AuthUserDisplayName == "認証ユーザ"
        assert status.CurrentInstanceId == "初期インスタンスID"
        assert status.CurrentWorldId == "初期ワールドID"
        assert status.CurrentWorldName == "初期ワールド名"
        assert status.VisitedWorldCount == 0

        status = main.LogParserStatus(0, 0, "認証ユーザ", None, None, None)
        with pytest.raises(main.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerLeft ユーザ名\n\n\n", "認証ユーザ", status)

    def test_proc_logevent_text_InitializedApi(self):
        status = main.LogParserStatus(
            0, 1, None, "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        res = main.VRChatLogReader.proc_logevent_text(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Initialized PlayerAPI \"認証ユーザ1\" is local\n\n\n", "認証ユーザ1", status)

        assert res.Type == main.LogEventType.InitializedApi
        assert status.AuthUserDisplayName == "認証ユーザ1"
        assert status.CurrentInstanceId == "初期インスタンスID"
        assert status.CurrentWorldId == "初期ワールドID"
        assert status.CurrentWorldName == "初期ワールド名"
        assert status.VisitedWorldCount == 1

        status = main.LogParserStatus(
            0, 1, None, "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        
        with pytest.raises(main.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] Initialized PlayerAPI \"認証ユーザ1\" is local\n\n\n", "認証ユーザ2", status)
        assert ex.value.reason == main.VRChatLogErrorType.MissMatchAuthUser

        status = main.LogParserStatus(
            0, 2, None, "初期ワールドID", "初期ワールド名", "初期インスタンスID")
        with pytest.raises(main.VRChatLogError) as ex:
            res = main.VRChatLogReader.proc_logevent_text(
                "2012.01.23 01:23:45 Log        -  [Behaviour] Initialized PlayerAPI \"認証ユーザ1\" is local\n\n\n", "認証ユーザ1", status)
        assert ex.value.reason == main.VRChatLogErrorType.InvalidStatus

    def test_parse_activity(self):
        status = main.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Entering Room: ワールド名\n\n\n", status
        )
        assert res.Type == main.LogEventType.EnterWorld
        assert res.Timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.InstanceId == "現在インスタンスID"
        assert res.WorldId == "現在ワールドID"
        assert res.WorldName == "ワールド名"

        status = main.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnLeftRoom\n\n\n", status
        )
        assert res.Type == main.LogEventType.LeftWorld
        assert res.Timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.InstanceId == "現在インスタンスID"
        assert res.WorldId == "現在ワールドID"
        assert res.WorldName == "現在ワールド名"

        status = main.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerJoined ユーザ名\n\n\n", status
        )
        assert res.Type == main.LogEventType.EnterPlayer
        assert res.Timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.InstanceId == "現在インスタンスID"
        assert res.WorldId == "現在ワールドID"
        assert res.WorldName == "現在ワールド名"
        assert res.UserDisplayName == "ユーザ名"

        status = main.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] Initialized PlayerAPI \"ユーザ名\"hogehoge\" is local", status
        )
        assert res.Type == main.LogEventType.InitializedApi
        assert res.Timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.InstanceId == "現在インスタンスID"
        assert res.WorldId == "現在ワールドID"
        assert res.WorldName == "現在ワールド名"
        assert res.UserDisplayName == "ユーザ名\"hogehoge"
        assert res.Mode == "local"

        status = main.LogParserStatus(0, 0, "認証ユーザ", "現在ワールドID", "現在ワールド名", "現在インスタンスID")
        res = main.VRChatLogReader.parse_activity(
            "2012.01.23 01:23:45 Log        -  [Behaviour] OnPlayerLeft ユーザ名\n\n\n", status
        )
        assert res.Type == main.LogEventType.LeftPlayer
        assert res.Timestamp == datetime.datetime(2012, 1, 23, 1, 23, 45)
        assert res.InstanceId == "現在インスタンスID"
        assert res.WorldId == "現在ワールドID"
        assert res.WorldName == "現在ワールド名"
        assert res.UserDisplayName == "ユーザ名"


class TestDynamoStore:
    def test_put_activity(self):
        store = main.DynamoStore(
            os.getenv("APP_GET_TABLE_NAME"),
            os.getenv("APP_PUT_TABLE_NAME"),
            boto3.Session()
        )

        log_type = main.LogEventType.JoiningInstance
        log_item = main.LogEventEnterWorld(
            log_type, datetime.datetime(2012, 1, 23, 1, 23, 45), "inst_id", "wrld_id", "ワールド名")
        store.put_activity(log_item, "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

        log_type = main.LogEventType.LeftWorld
        log_item = main.LogEventLeftWorld(
            log_type, datetime.datetime(2012, 1, 23, 1, 23, 45), "inst_id", "wrld_id", "ワールド名")
        store.put_activity(log_item, "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

        log_type = main.LogEventType.EnterPlayer
        log_item = main.LogEventEnterPlayer(
            log_type, datetime.datetime(2012, 1, 23, 1, 23, 45), "inst_id", "wrld_id", "ワールド名", "ユーザ名")
        store.put_activity(log_item, "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")

        log_type = main.LogEventType.LeftPlayer
        log_item = main.LogEventLeftPlayer(
            log_type, datetime.datetime(2012, 1, 23, 1, 23, 45), "inst_id", "wrld_id", "ワールド名", "ユーザ名")
        store.put_activity(log_item, "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx")


class TestApp:
    def setup(self):
        pth = Path("tests/sandbox/checkpoint")
        shutil.rmtree(pth, ignore_errors=True)
        pth.mkdir(parents=True, exist_ok=True)

    def test_invoke(self):
        app_get_dir = Path("./tests/data").resolve()
        app_put_dir = Path("./tests/sandbox").resolve()
        app = main.App(app_get_dir, app_put_dir, "sample")
        vrc = main.VRChatResource(app.log_dir)
        dyn = main.DynamoStore(
            os.getenv("APP_GET_TABLE_NAME"),
            os.getenv("APP_PUT_TABLE_NAME"),
            boto3.Session()
        )
        app.init(vrc, dyn)
        app.invoke()

    def test_get_status(self):
        status = main.App.get_status(Path("tests/data"), "sample")
        assert len(status) == 3

        obj = status["log_01.txt"]
        assert obj.AuthUserDisplayName == "hoge"
        assert obj.CurrentInstanceId == "99999"
        assert obj.CurrentWorldId ==  "wrld_xxx"
        assert obj.CurrentWorldName == "ワールド名"
        assert obj.Pos == 123
        assert obj.VisitedWorldCount == 1

        obj = status["log_02.txt"]
        assert obj.AuthUserDisplayName == "hoge"
        assert obj.CurrentInstanceId == "99999"
        assert obj.CurrentWorldId ==  "wrld_xxx"
        assert obj.CurrentWorldName == "ワールド名"
        assert obj.Pos == 123
        assert obj.VisitedWorldCount == 1

        obj = status["log_03.txt"]
        assert obj.AuthUserDisplayName == "hoge"
        assert obj.CurrentInstanceId == "99999"
        assert obj.CurrentWorldId ==  "wrld_xxx"
        assert obj.CurrentWorldName == "ワールド名"
        assert obj.Pos == 123
        assert obj.VisitedWorldCount == 1

    def test_set_status(self):
        main.App.set_status(Path("tests/sandbox"), "sample", {
            "log_01.txt": main.LogParserStatus(123, 0, "認証ユーザ", "ワールドID1", "ワールド名1", "インスタンスID1"),
            "log_02.txt": main.LogParserStatus(234, 0, "認証ユーザ", "ワールドID2", "ワールド名2", "インスタンスID2"),
            "log_03.txt": main.LogParserStatus(345, 0, "認証ユーザ", "ワールドID3", "ワールド名3", "インスタンスID3"),
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
