import boto3
import json
import logging
import os
from datetime import datetime
from typing import Iterable
from common import entity, dynamodb, sqs, vrchat

logger = logging.getLogger(__name__)


class App:
    def __init__(self, vrc: vrchat.Service, db: dynamodb.Service, sqs: sqs.ProcesserService):
        self._vrc = vrc
        self._dyn = db
        self._sqs = sqs

    def invoke(self, update_date: datetime):
        current_user_info = self._vrc.get_current_user()
        friends_in_vrc = self._vrc.get_friends(current_user_info, update_date)
        friends_in_dyn = self._dyn.get_friends()

        for item in extract_change_friends(friends_in_dyn, friends_in_vrc, update_date):
            self._dyn.put_friend(item)
            self._sqs.enqueue(item)
        

def extract_change_friends(infos_old: list[entity.FriendInfo], infos_new: list[entity.FriendInfo], update_date: datetime) -> Iterable[entity.OperationInfo]:
    i_old, i_new = 0, 0
    while i_old < len(infos_old) or i_new < len(infos_new):
        info_old_dt: entity.FriendInfo = None
        info_old_id = "zzz"
        if i_old < len(infos_old):
            info_old_dt = infos_old[i_old]
            info_old_id = info_old_dt.user_id

        info_new_dt: entity.FriendInfo = None
        info_new_id = "zzz"
        if i_new < len(infos_new):
            info_new_dt = infos_new[i_new]
            info_new_id = info_new_dt.user_id

        # 更新を抽出
        if info_old_id == info_new_id:
            if info_old_dt != info_new_dt:
                info_new_dt.regist_date = info_old_dt.regist_date
                yield entity.OperationInfo(entity.ActionType.UPDATE, info_new_dt, info_old_dt)
            i_old += 1
            i_new += 1
        # 削除を抽出
        elif info_old_id < info_new_id:
            info_old_dt.update_date = int(update_date.timestamp())
            yield entity.OperationInfo(entity.ActionType.REMOVE, None, info_old_dt)
            i_old += 1
        # 追加を抽出
        else:
            info_new_dt.regist_date = int(update_date.timestamp())
            yield entity.OperationInfo(entity.ActionType.ADD, info_new_dt, None)
            i_new += 1


def lambda_handler(event, context):
    APP_GET_TABLE_NAME = os.getenv("APP_GET_TABLE_NAME")
    APP_PUT_TABLE_NAME = os.getenv("APP_PUT_TABLE_NAME")
    PROCESSER_PUT_QUEUE = os.getenv("PROCESSER_PUT_QUEUE")

    for job in event["Records"]:
        # キューイングされた情報を取得
        job_info = json.loads(job["body"])
        account_id = job_info["account_id"]

        # 前回処理時の認証情報が有れば取得
        sess = boto3.Session()
        res_db = dynamodb.Service(account_id, APP_GET_TABLE_NAME, APP_PUT_TABLE_NAME, sess, logger)
        acc = res_db.get_account()

        # 本処理
        update_date = datetime.now()
        sess = boto3.Session()
        res_sqs = sqs.ProcesserService(account_id, PROCESSER_PUT_QUEUE, sess, logger)
        res_vrc = vrchat.Service(acc.vrchat_user_name, acc.vrchat_passwd, acc.cookies)
        app = App(res_vrc, res_db, res_sqs)
        app.invoke(update_date)

        # 後始末
        res_db.put_account(acc, update_date)
