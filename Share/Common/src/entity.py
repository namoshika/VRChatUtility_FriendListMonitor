import enum
import json
from dataclasses import dataclass
from datetime import datetime
from enum import Enum, auto


class ActionType(enum.Enum):
    ADD = enum.auto()
    UPDATE = enum.auto()
    REMOVE = enum.auto()


class LogEventType(Enum):
    ENTER_WORLD = auto()
    ENTER_PLAYER = auto()
    LEFT_WORLD = auto()
    LEFT_PLAYER = auto()
    JOIN_INSTANCE = auto()
    INITIALIZE_API = auto()


class VRChatLogErrorType(Enum):
    INVALID_STATUS = auto()
    MISS_MATCH_AUTHUSER = auto()
    LOG_BUFFER_OVERFLOW = auto()


@dataclass
class FriendInfo:
    user_id: str
    user_name: str
    user_display_name: str
    regist_date: int
    update_date: int

    def __eq__(self, other) -> bool:
        return self.user_id == other.user_id \
            and self.user_name == other.user_name \
            and self.user_display_name == other.user_display_name

    def __lt__(self, other) -> bool:
        return self.user_id < other.user_id


@dataclass
class OperationInfo:
    action: ActionType
    info_new: FriendInfo
    info_old: FriendInfo


@dataclass
class LogEvent:
    type: LogEventType
    timestamp: datetime


@dataclass
class LogEventEnterWorld(LogEvent):
    instance_id: str
    world_id: str
    world_name: str


@dataclass
class LogEventLeftWorld(LogEvent):
    type = LogEventType.LEFT_WORLD
    instance_id: str
    world_id: str
    world_name: str


@dataclass
class LogEventEnterPlayer(LogEvent):
    type = LogEventType.ENTER_PLAYER
    instance_id: str
    world_id: str
    world_name: str
    user_display_name: str


@dataclass
class LogEventLeftPlayer(LogEvent):
    type = LogEventType.LEFT_PLAYER
    instance_id: str
    world_id: str
    world_name: str
    user_display_name: str


@dataclass
class LogEventInitializedApi(LogEvent):
    type = LogEventType.INITIALIZE_API
    instance_id: str
    world_id: str
    world_name: str
    user_display_name: str
    mode: str


@dataclass
class LogParserStatus:
    pos: int
    visited_world_count: int
    authuser_display_name: str
    current_world_id: str
    current_world_name: str
    current_instance_id: str

    def update(self, new_value) -> None:
        self.pos = new_value.pos
        self.visited_world_count = new_value.visited_world_count
        self.authuser_display_name = new_value.authuser_display_name
        self.current_world_id = new_value.current_world_id
        self.current_world_name = new_value.current_world_name
        self.current_instance_id = new_value.current_instance_id


class VRChatLogError(Exception):
    def __init__(self, reason: VRChatLogErrorType, message: str):
        self.reason = reason
        self.message = message


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
                "action": o.action.name,
                "info_new": o.info_new,
                "info_old": o.info_old
            }
        else:
            return super().default(o)


class CustomJsonDecoder(json.JSONDecoder):
    ACTION_TYPE_DICT = {
        "ADD": ActionType.ADD,
        "REMOVE": ActionType.REMOVE,
        "UPDATE": ActionType.UPDATE
    }

    def object_hock(self, o):
        if "_type" not in o:
            return o

        typ = o["_type"]
        if typ == "FriendInfo":
            return FriendInfo(o["user_id"], o["user_name"], o["user_display_name"], o["regist_date"], o["update_date"])
        if typ == "OperationInfo":
            return OperationInfo(self.ACTION_TYPE_DICT[o["action"]], o["info_new"], o["info_old"])
