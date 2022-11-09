import boto3
import logging
import os
import sys
import pytest
from pathlib import Path

sys.path.append("src")
logger = logging.getLogger(__name__)


class TestAccountManager:
    def test_vrchat(self):
        from . import core
        ACCOUNT_ID = "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        APP_PUT_TABLE_NAME = os.getenv("APP_PUT_TABLE_NAME")

        acc = core.AccountManager()
        acc.connect_vrchat(ACCOUNT_ID, APP_PUT_TABLE_NAME, "sample_user", "sample_passwd")
        acc.connect_notion(ACCOUNT_ID, APP_PUT_TABLE_NAME, "sample_token", "sample_dbid")
        acc.disconnect_notion(ACCOUNT_ID, APP_PUT_TABLE_NAME)
        acc.disconnect_vrchat(ACCOUNT_ID, APP_PUT_TABLE_NAME)


class TestFriendManager:
    def test_crud(self):
        from . import core
        from src.common import dynamodb

        ACCOUNT_ID = "usr_xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        APP_GET_TABLE_NAME = os.getenv("APP_GET_TABLE_NAME")
        APP_PUT_TABLE_NAME = os.getenv("APP_PUT_TABLE_NAME")
        app_dir = (Path(__file__) / "../../").resolve()
        sess = boto3.Session()
        dyn = dynamodb.Service(ACCOUNT_ID, APP_GET_TABLE_NAME, APP_PUT_TABLE_NAME, sess, logger)

        import_path = app_dir / "tests/data/import_friendlist.csv"
        target = core.FriendManager()
        target.import_csv(ACCOUNT_ID, APP_GET_TABLE_NAME, import_path)

        export_path = app_dir / "tests/sandbox/export_friendlist.csv"
        target.export_csv(ACCOUNT_ID, APP_GET_TABLE_NAME, export_path)

        import_txt = import_path.read_text()
        export_txt = export_path.read_text()
        assert import_txt == export_txt

        target.clear_all(ACCOUNT_ID, APP_GET_TABLE_NAME)
        assert len(dyn.get_friends()) == 0
