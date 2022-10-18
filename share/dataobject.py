import enum
import json
from dataclasses import dataclass

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
    ACTION_TYPE_DICT = {
        "Add": ActionType.Add,
        "Remove": ActionType.Remove,
        "Update": ActionType.Update
    }
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
                self.ACTION_TYPE_DICT[o["action_type"]], o["info_new"], o["info_old"])
