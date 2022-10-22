import boto3
import dataclasses
import datetime
import json
import logging
import re
import sys
import time
import traceback
from argparse import ArgumentParser
from configparser import ConfigParser
from enum import Enum, auto
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Iterable, Tuple

import schedule

log_dir = Path(__file__) / "../../log"
log_dir = log_dir.resolve()
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / "main.log"
log_level = logging.INFO

logger = logging.getLogger(__name__)
logger.setLevel(log_level)
log_hand = RotatingFileHandler(log_file, maxBytes=5242880, backupCount=3, encoding="utf-8")
log_hand.setLevel(log_level)
log_form = logging.Formatter(
    "%(asctime)s %(levelname)s - %(filename)s.%(name)s.%(funcName)s - %(message)s", "%Y-%m-%dT%H:%M:%S")
log_hand.setFormatter(log_form)
logger.addHandler(log_hand)


class LogEventType(Enum):
    EnterWorld = auto()
    EnterPlayer = auto()
    LeftWorld = auto()
    LeftPlayer = auto()
    JoiningInstance = auto()
    InitializedApi = auto()


class VRChatLogErrorType(Enum):
    InvalidStatus = auto()
    MissMatchAuthUser = auto()
    LogBufferOverflow = auto()


@dataclasses.dataclass
class LogEvent:
    Type: LogEventType
    Timestamp: datetime.datetime


@dataclasses.dataclass
class LogEventEnterWorld(LogEvent):
    InstanceId: str
    WorldId: str
    WorldName: str


@dataclasses.dataclass
class LogEventLeftWorld(LogEvent):
    Type = LogEventType.LeftWorld
    InstanceId: str
    WorldId: str
    WorldName: str


@dataclasses.dataclass
class LogEventEnterPlayer(LogEvent):
    Type = LogEventType.EnterPlayer
    InstanceId: str
    WorldId: str
    WorldName: str
    UserDisplayName: str


@dataclasses.dataclass
class LogEventLeftPlayer(LogEvent):
    Type = LogEventType.LeftPlayer
    InstanceId: str
    WorldId: str
    WorldName: str
    UserDisplayName: str


@dataclasses.dataclass
class LogEventInitializedApi(LogEvent):
    Type = LogEventType.InitializedApi
    InstanceId: str
    WorldId: str
    WorldName: str
    UserDisplayName: str
    Mode: str


@dataclasses.dataclass
class LogParserStatus:
    Pos: int
    VisitedWorldCount: int
    AuthUserDisplayName: str
    CurrentWorldId: str
    CurrentWorldName: str
    CurrentInstanceId: str

    def update(self, new_value) -> None:
        self.Pos = new_value.Pos
        self.VisitedWorldCount = new_value.VisitedWorldCount
        self.AuthUserDisplayName = new_value.AuthUserDisplayName
        self.CurrentWorldId = new_value.CurrentWorldId
        self.CurrentWorldName = new_value.CurrentWorldName
        self.CurrentInstanceId = new_value.CurrentInstanceId


class VRChatLogError(Exception):
    def __init__(self, reason: VRChatLogErrorType, message: str):
        self.reason = reason
        self.message = message


class VRChatResource:
    def __init__(self, log_dir: Path):
        self._log_dir = log_dir

    def read_log(self, target_user: str, configs: dict[str, LogParserStatus]) -> Iterable[LogEvent]:
        # 読込み対象を決定
        dir = self._log_dir
        items = [(dir / file, conf) for file, conf in configs.items()]
        items = [(path, path.stat(), conf) for path, conf in items]
        items.sort(key=lambda val: val[1].st_size)
        count = len(items)
        items = [(path, conf, i != count - 1) for i, (path, stat, conf) in enumerate(items)]

        # ログリーダーを作成 (最新ログは最後の行まで読まない)
        logger.info(f"ログファイルを検知 (Files Count: {count}).")
        readers = [VRChatLogReader(path, last, target_user, conf) for path, conf, last in items]
        # ログを古い方から順次読み込み
        for log in readers:
            try:
                for log_item in log.read():
                    yield log_item
            except FileNotFoundError as ex:
                # 処理中にファイルが消去された場合は読み込みをスキップ
                msg = f"ログ (\"{log._logfile_path}\") の解析がスキップされました. ファイルが見つかりません.\n{get_stacktrace()}\n"
                logger.warning(msg)
            except Exception as ex:
                msg = f"ログ (\"{log._logfile_path}\") の解析が中断されました. 予期しない例外がスローされています.\n{get_stacktrace()}\n"
                logger.error(msg)
                raise

class VRChatLogReader:
    LOG_BUFFER_SIZE = 102_400
    REGEX_LOG_MSG = re.compile(
        r"\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2}[^-]+-")
    REGEX_ENTER_WORLD_01 = re.compile(
        r"^(?P<Timestamp>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})[^-]+-  \[Behaviour\] Entering Room: (?P<WorldName>[^\n]+)")
    REGEX_ENTER_WORLD_02 = re.compile(
        r"^(?P<Timestamp>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})[^-]+-  \[Behaviour\] Joining (?P<WorldId>wrld_[^:]+):(?P<InstanceId>[^\n]+)")
    REGEX_PLAYER_JOINED = re.compile(
        r"^(?P<Timestamp>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})[^-]+-  \[Behaviour\] OnPlayerJoined (?P<UserName>[^\n]+)")
    REGEX_INITIALIZED_API = re.compile(
        r"^(?P<Timestamp>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})[^-]+-  \[Behaviour\] Initialized PlayerAPI \"(?P<UserName>.*)\" is (?P<Mode>[^\n]+)")
    REGEX_PLAYER_LEFT = re.compile(
        r"^(?P<Timestamp>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})[^-]+-  \[Behaviour\] OnPlayerLeft (?P<UserName>[^\n]+)")
    REGEX_LEFT_WORLD = re.compile(
        r"^(?P<Timestamp>\d{4}\.\d{2}\.\d{2} \d{2}:\d{2}:\d{2})[^-]+-  \[Behaviour\] OnLeftRoom")

    def __init__(self, logfile_path: Path, is_read_lastlog: bool, target_user: str, status: LogParserStatus):
        self._logfile_path = logfile_path
        self._is_read_lastlog = is_read_lastlog
        self._target_user = target_user
        self._status = status
        self._log_buff = list()

    def read(self) -> Iterable[LogEvent]:
        try:
            # 未読込み分のみ処理する
            # TODO: 追加分を読む際にAuthUserが取得できないはず
            file_pos = self._status.Pos
            file_sta = self._logfile_path.stat()
            if file_sta.st_size <= file_pos:
                return

            logger.info(f"ログ (\"{str(self._logfile_path)}\") の解析を開始.")
            log_stream = self._logfile_path.open(mode="r", encoding="utf8", errors="replace")
            log_stream.seek(file_pos)
            status = dataclasses.replace(self._status)
            for activity in self.read_log(log_stream, self._is_read_lastlog, self._target_user, status):
                if status.AuthUserDisplayName != self._target_user:
                    if status.Pos >= self.LOG_BUFFER_SIZE:
                        raise VRChatLogError(
                            VRChatLogErrorType.LogBufferOverflow,
                            f"ログ生成時のログインユーザを特定できませんでした (Over {self.LOG_BUFFER_SIZE} Bytes)"
                        )
                    self._log_buff.append((dataclasses.replace(status), activity))
                else:
                    if len(self._log_buff) > 0:
                        self._log_buff.append((status, activity))
                        for buff_status, buff_activity in self._log_buff:
                            self._status.update(buff_status)
                            yield buff_activity
                        self._log_buff.clear()
                    else:
                        self._status.update(status)
                        yield activity

            if len(self._log_buff) > 0:
                raise VRChatLogError(
                    VRChatLogErrorType.LogBufferOverflow, "ログ生成時のログインユーザを特定できませんでした")

        except VRChatLogError as ex:
            self._status.update(status)
            if ex.reason == VRChatLogErrorType.MissMatchAuthUser:
                return
            if ex.reason == VRChatLogErrorType.LogBufferOverflow:
                msg = f"ログ (\"{str(self._logfile_path)}\") の解析がスキップされました. ログインユーザが不明です.\n{get_stacktrace()}\n"
                logger.warning(msg)
                return
            raise

    @staticmethod
    def read_log(log_stream, is_read_lastlog: bool, target_user: str, status: LogParserStatus) -> Iterable[Tuple[int, str]]:
        buffer = ""
        for line in log_stream:
            buffer += line
            prev_index = 0
            for match_res in VRChatLogReader.REGEX_LOG_MSG.finditer(buffer):
                start_pos = match_res.start()
                if prev_index != start_pos:
                    m_txt = buffer[prev_index:start_pos]
                    activity = VRChatLogReader.proc_logevent_text(m_txt, target_user, status)

                    if activity is not None:
                        yield activity

                prev_index = start_pos
            buffer = buffer[prev_index:]

        if is_read_lastlog:
            activity = VRChatLogReader.proc_logevent_text(buffer, target_user, status)
            if activity is not None:
                yield activity

    @staticmethod
    def proc_logevent_text(text: str, target_user: str, status: LogParserStatus) -> LogEvent:
        # ログを正規化した上でパース
        text_normalized = text.replace("\r", "").strip()
        activity = VRChatLogReader.parse_activity(text_normalized, status)

        # パースされた場合はステートを更新
        if isinstance(activity, LogEventEnterWorld):
            if activity.Type == LogEventType.EnterWorld:
                status.CurrentInstanceId = None
                status.CurrentWorldId = None
                status.CurrentWorldName = activity.WorldName
                activity = None
            elif activity.Type == LogEventType.JoiningInstance:
                status.CurrentInstanceId = activity.InstanceId
                status.CurrentWorldId = activity.WorldId
                status.CurrentWorldName = activity.WorldName
                status.VisitedWorldCount += 1
            else:
                raise VRChatLogError(
                    VRChatLogErrorType.InvalidStatus, "ログがプログラムの想定しない状態になっています"
                )
        elif isinstance(activity, LogEventEnterPlayer):
            if status.CurrentInstanceId is None \
                    or status.CurrentWorldId is None \
                    or status.CurrentWorldName is None:
                raise VRChatLogError(
                    VRChatLogErrorType.InvalidStatus, "ログがプログラムの想定しない状態になっています"
                )
        elif isinstance(activity, LogEventLeftWorld):
            if status.CurrentInstanceId is None \
                    or status.CurrentWorldId is None \
                    or status.CurrentWorldName is None:
                raise VRChatLogError(
                    VRChatLogErrorType.InvalidStatus, "ログがプログラムの想定しない状態になっています"
                )
        elif isinstance(activity, LogEventLeftPlayer):
            if status.CurrentInstanceId is None \
                    or status.CurrentWorldId is None \
                    or status.CurrentWorldName is None:
                raise VRChatLogError(
                    VRChatLogErrorType.InvalidStatus,
                    "ログがプログラムの想定しない状態になっています (現在のワールドが取得される前にその他のログが出力されました)"
                )
        elif isinstance(activity, LogEventInitializedApi):
            if activity.Mode == "local":
                if status.AuthUserDisplayName is None and status.VisitedWorldCount <= 1:
                    if activity.UserDisplayName != target_user:
                        raise VRChatLogError(
                            VRChatLogErrorType.MissMatchAuthUser, "ログ生成時のログインユーザが対象ユーザと異なります"
                        )
                    status.AuthUserDisplayName = activity.UserDisplayName
                elif status.AuthUserDisplayName is None and status.VisitedWorldCount > 1 or status.AuthUserDisplayName != activity.UserDisplayName:
                    raise VRChatLogError(
                        VRChatLogErrorType.InvalidStatus,
                        "ログがプログラムの想定しない状態になっています (PlayerAPI へ想定外の初期化が行われました)"
                    )

        # パースされたログを出力
        status.Pos += len(text.encode("utf8"))
        return activity

    @staticmethod
    def parse_activity(log_item: str, status: LogParserStatus) -> LogEvent:
        if log_item == "" or log_item[34:45] != "[Behaviour]":
            return None
        elif match_res := VRChatLogReader.REGEX_ENTER_WORLD_01.match(log_item):
            timestamp = match_res.group("Timestamp")
            worldName = match_res.group("WorldName")
            timestamp = datetime.datetime.strptime(timestamp, "%Y.%m.%d %H:%M:%S")
            return LogEventEnterWorld(
                Type=LogEventType.EnterWorld,
                Timestamp=timestamp,
                InstanceId=status.CurrentInstanceId,
                WorldId=status.CurrentWorldId,
                WorldName=worldName
            )
        elif match_res := VRChatLogReader.REGEX_ENTER_WORLD_02.match(log_item):
            timestamp = match_res.group("Timestamp")
            instance_id = match_res.group("InstanceId")
            world_id = match_res.group("WorldId")
            timestamp = datetime.datetime.strptime(timestamp, "%Y.%m.%d %H:%M:%S")
            return LogEventEnterWorld(
                Type=LogEventType.JoiningInstance,
                Timestamp=timestamp,
                InstanceId=instance_id,
                WorldId=world_id,
                WorldName=status.CurrentWorldName
            )
        elif match_res := VRChatLogReader.REGEX_LEFT_WORLD.match(log_item):
            timestamp = match_res.group("Timestamp")
            timestamp = datetime.datetime.strptime(timestamp, "%Y.%m.%d %H:%M:%S")
            return LogEventLeftWorld(
                Type=LogEventType.LeftWorld,
                Timestamp=timestamp,
                InstanceId=status.CurrentInstanceId,
                WorldId=status.CurrentWorldId,
                WorldName=status.CurrentWorldName
            )
        elif match_res := VRChatLogReader.REGEX_PLAYER_JOINED.match(log_item):
            timestamp = match_res.group("Timestamp")
            userName = match_res.group("UserName")
            timestamp = datetime.datetime.strptime(timestamp, "%Y.%m.%d %H:%M:%S")
            return LogEventEnterPlayer(
                Type=LogEventType.EnterPlayer,
                Timestamp=timestamp,
                InstanceId=status.CurrentInstanceId,
                WorldId=status.CurrentWorldId,
                WorldName=status.CurrentWorldName,
                UserDisplayName=userName
            )
        elif match_res := VRChatLogReader.REGEX_PLAYER_LEFT.match(log_item):
            timestamp = match_res.group("Timestamp")
            userName = match_res.group("UserName")
            timestamp = datetime.datetime.strptime(timestamp, "%Y.%m.%d %H:%M:%S")
            return LogEventLeftPlayer(
                Type=LogEventType.LeftPlayer,
                Timestamp=timestamp,
                InstanceId=status.CurrentInstanceId,
                WorldId=status.CurrentWorldId,
                WorldName=status.CurrentWorldName,
                UserDisplayName=userName
            )
        elif match_res := VRChatLogReader.REGEX_INITIALIZED_API.match(log_item):
            timestamp = match_res.group("Timestamp")
            userName = match_res.group("UserName")
            api_mode = match_res.group("Mode")
            timestamp = datetime.datetime.strptime(timestamp, "%Y.%m.%d %H:%M:%S")
            return LogEventInitializedApi(
                Type=LogEventType.InitializedApi,
                Timestamp=timestamp,
                InstanceId=status.CurrentInstanceId,
                WorldId=status.CurrentWorldId,
                WorldName=status.CurrentWorldName,
                UserDisplayName=userName,
                Mode=api_mode
            )
        else:
            return None


class DynamoStore:
    SUFFIX_LEN: int = 3

    def __init__(self, get_table_name: str, put_table_name: str, aws_sess: boto3.Session):
        self.dynamodb = aws_sess.client("dynamodb")
        self.dynamodb_res = aws_sess.resource("dynamodb")
        self._get_table = self.dynamodb_res.Table(get_table_name)
        self._put_table = self.dynamodb_res.Table(put_table_name)

    def put_activity(self, activity: LogEvent, account_id: str) -> None:
        timestamp_id = activity.Timestamp.strftime("%Y%m%d_%H%M%S")
        timestamp_text = activity.Timestamp.strftime("%Y.%m.%d %H:%M:%S")
        # レコード有効期限を秒単位の UNIXTIME として生成
        expiration_time = datetime.datetime.now()
        expiration_time = expiration_time + datetime.timedelta(hours=24)
        expiration_time = int(expiration_time.timestamp())

        i = 0
        while True:
            try:
                if isinstance(activity, LogEventEnterWorld):
                    val_sk = f"#activity:world.enter#timestamp:{timestamp_id}"
                    val_suffix = sum(val_sk.encode()) % self.SUFFIX_LEN
                    self._put_table.put_item(Item={
                        "pk": f"#account:{account_id}#suffix:{val_suffix}",
                        "sk": val_sk,
                        "instance_id": activity.InstanceId,
                        "world_id": activity.WorldId,
                        "world_name": activity.WorldName,
                        "timestamp": timestamp_text,
                        "expiration_time": expiration_time
                    })
                elif isinstance(activity, LogEventLeftWorld):
                    val_sk = f"#activity:world.left#timestamp:{timestamp_id}"
                    val_suffix = sum(val_sk.encode()) % self.SUFFIX_LEN
                    self._put_table.put_item(Item={
                        "pk": f"#account:{account_id}#suffix:{val_suffix}",
                        "sk": val_sk,
                        "instance_id": activity.InstanceId,
                        "world_id": activity.WorldId,
                        "world_name": activity.WorldName,
                        "timestamp": timestamp_text,
                        "expiration_time": expiration_time
                    })
                elif isinstance(activity, LogEventEnterPlayer):
                    username_esc = activity.UserDisplayName
                    username_esc = username_esc.replace("\\", "\\\\")
                    username_esc = username_esc.replace("#", "\\u0023")
                    username_esc = username_esc.replace(":", "\\u003a")
                    val_sk = f"#activity:user.enter.{username_esc}#timestamp:{timestamp_id}"
                    val_suffix = sum(val_sk.encode()) % self.SUFFIX_LEN
                    self._put_table.put_item(Item={
                        "pk": f"#account:{account_id}#suffix:{val_suffix}",
                        "sk": val_sk,
                        "instance_id": activity.InstanceId,
                        "world_id": activity.WorldId,
                        "world_name": activity.WorldName,
                        "user_name": activity.UserDisplayName,
                        "timestamp": timestamp_text,
                        "expiration_time": expiration_time
                    })
                elif isinstance(activity, LogEventLeftPlayer):
                    username_esc = activity.UserDisplayName
                    username_esc = username_esc.replace("\\", "\\\\")
                    username_esc = username_esc.replace("#", "\\u0023")
                    username_esc = username_esc.replace(":", "\\u003a")
                    val_sk = f"#activity:user.left.{username_esc}#timestamp:{timestamp_id}"
                    val_suffix = sum(val_sk.encode()) % self.SUFFIX_LEN
                    self._put_table.put_item(Item={
                        "pk": f"#account:{account_id}#suffix:{val_suffix}",
                        "sk": val_sk,
                        "instance_id": activity.InstanceId,
                        "world_id": activity.WorldId,
                        "world_name": activity.WorldName,
                        "user_name": activity.UserDisplayName,
                        "timestamp": timestamp_text,
                        "expiration_time": expiration_time
                    })
                break
            except self.dynamodb.exceptions.ProvisionedThroughputExceededException as ex:
                if i > 1:
                    logger.warning("DynamoDB 書き込みでキャパシティ超過を起因とした複数回のエラーが発生.")
                    raise
                else:
                    logger.warning("DynamoDB 書き込みでキャパシティ超過を起因とした複数回のエラーが発生 (10秒後に再試行).")
                    time.sleep(10)


class App:
    SET_STATUS_INTERVAL = datetime.timedelta(seconds=20)

    def __init__(self, app_get_dir: Path, app_put_dir: Path, profile: str):
        self._app_get_dir = app_get_dir
        self._app_put_dir = app_put_dir
        self._profile = profile

        config = ConfigParser()
        config.read(app_get_dir / "config/setting.ini")
        self._logdir = Path(config.get(f"profile.{profile}", "log_dir"))
        self._account_id = config.get(f"profile.{profile}", "account_id")
        self._account_name = config.get(f"profile.{profile}", "account_name")
        self._get_table_name = config.get(f"profile.{profile}", "get_table_name")
        self._put_table_name = config.get(f"profile.{profile}", "put_table_name")
        self._put_queue_name = config.get(f"profile.{profile}", "put_queue_name")
        self._is_enabled_ewq = config.get(f"profile.{profile}", "enqueue_worker_queue") == "enabled"
        self._status = self.get_status(app_get_dir, profile)
        self._check_interval_sec = int(config.get(f"profile.{profile}", "check_interval_sec"))

        aws_access_key_id = config.get(f"profile.{profile}", "aws_access_key_id")
        aws_secret_access_key = config.get(f"profile.{profile}", "aws_secret_access_key")
        self._aws_sess = boto3.Session(aws_access_key_id=aws_access_key_id,
                                       aws_secret_access_key=aws_secret_access_key)

    @property
    def check_interval_sec(self): return self._check_interval_sec
    @property
    def log_dir(self): return self._logdir
    @property
    def get_table_name(self): return self._get_table_name
    @property
    def put_table_name(self): return self._put_table_name
    @property
    def aws_sess(self): return self._aws_sess

    def init(self, vrc_client: VRChatResource, dynamo_store: DynamoStore):
        self._vrc = vrc_client
        self._dynamo = dynamo_store

    def invoke(self):
        logger.info("ログ解析処理を開始")

        # 各ログファイルの読込み済みバイト数の記録を取得
        # 存在しないログファイルの読込み済みバイト数の記録は削除
        self._status = {
            f.name: self._status.get(f.name) or LogParserStatus(0, 0, None, None, None, None)
            for f in self._logdir.glob("output_log_*.txt") if f.is_file()
        }

        # 各ログファイルを処理
        old_time = datetime.datetime.min
        count = 0
        is_modified = False
        is_moveworld = False
        for activity in self._vrc.read_log(self._account_name, self._status):
            # DB へアクティビティを転送
            self._dynamo.put_activity(activity, self._account_id)

            # 進捗を記録 (途中。10秒置きに記録)
            newTime = datetime.datetime.now()
            if newTime - old_time > self.SET_STATUS_INTERVAL:
                self.set_status(self._app_put_dir, self._profile, self._status)
                old_time = newTime

            count += 1
            is_modified = True
            is_moveworld |= activity.Type == LogEventType.EnterWorld or activity.Type == LogEventType.LeftWorld

        # 進捗を記録 (最後)
        print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} ... ログをアップロード ({count} 件)")
        if is_modified:
            self.set_status(self._app_put_dir, self._profile, self._status)
        if is_moveworld and self._is_enabled_ewq:
            print(f"{datetime.datetime.now():%Y-%m-%d %H:%M:%S} ... Worker へキューイング")
            logger.info(f"Worker ({self._put_queue_name}) へキューイング")
            self.enqueue_worker(self._put_queue_name, self._account_id, self.aws_sess)

        logger.info(f"ログ解析処理を完了 ({count} 件)")

    @staticmethod
    def enqueue_worker(queue_name: str, account_id: str, aws_sess: boto3.Session):
        job_info = {"user_id": account_id}
        job_json = json.dumps(job_info, ensure_ascii=False)

        sqs = aws_sess.resource("sqs")
        vfe_queue = sqs.get_queue_by_name(QueueName=queue_name)
        vfe_queue.send_message(
            MessageBody=job_json,
            MessageAttributes={
                "Type": {"DataType": "String", "StringValue": "InvokeFunction"}
            }
        )

    @staticmethod
    def get_status(app_dir: Path, profile: str) -> dict[str, LogParserStatus]:
        cp_filepath = app_dir / f"checkpoint/{profile}.json"
        cp_filepath = cp_filepath.resolve()
        try:
            cp_obj = cp_filepath.read_text(encoding="utf8")
            cp_obj = json.loads(cp_obj, object_hook=App.json_dec)
            return cp_obj
        except FileNotFoundError as ex:
            return dict()

    @staticmethod
    def set_status(app_dir: Path, profile: str, value: dict[str, LogParserStatus]) -> None:
        cp_filepath = app_dir / f"checkpoint/{profile}.json"
        cp_filepath = cp_filepath.resolve()
        cp_text = json.dumps(value, ensure_ascii=False, indent=2, default=App.json_enc)
        cp_filepath.write_text(cp_text, encoding="utf8")

    @staticmethod
    def json_dec(o):
        if "_type" not in o:
            return o

        typ = o["_type"]
        if typ == "LogParserStatus":
            return LogParserStatus(
                o["Pos"],
                o["VisitedWorldCount"],
                o["AuthUserDisplayName"],
                o["CurrentWorldId"],
                o["CurrentWorldName"],
                o["CurrentInstanceId"]
            )

    @staticmethod
    def json_enc(o):
        if isinstance(o, LogParserStatus):
            return {
                "_type": "LogParserStatus",
                "Pos": o.Pos,
                "VisitedWorldCount": o.VisitedWorldCount,
                "AuthUserDisplayName": o.AuthUserDisplayName,
                "CurrentWorldId": o.CurrentWorldId,
                "CurrentWorldName": o.CurrentWorldName,
                "CurrentInstanceId": o.CurrentInstanceId
            }
        else:
            return super().default(o)

def get_stacktrace() -> str:
    t, v, tb = sys.exc_info()
    stacktrace = "".join(traceback.format_exception(t, v, tb))
    return stacktrace

if __name__ == "__main__":
    app_dir = Path(__file__) / "../../"
    app_dir = app_dir.resolve()

    parser = ArgumentParser()
    parser.add_argument("-p", "--profile", default="default", required=False)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    arg_watch = args.watch
    arg_profile = args.profile

    app = App(app_dir, app_dir, arg_profile)
    vrc = VRChatResource(app.log_dir)
    dyn = DynamoStore(app.get_table_name, app.put_table_name, app.aws_sess)
    app.init(vrc, dyn)

    if arg_watch == False:
        app.invoke()
    else:
        schedule.every(app.check_interval_sec).seconds.do(app.invoke)
        schedule.run_all()
        while True:
            schedule.run_pending()
            time.sleep(1)
