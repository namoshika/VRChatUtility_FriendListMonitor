import datetime
import logging
import os
import sys

sys.path.append("src")
import src.vrchat

class TestService:
    def test_api(self):
        vrc_username = os.getenv("VRCHAT_USERNAME")
        vrc_password = os.getenv("VRCHAT_PASSWORD")
        vrchat = src.vrchat.Service(vrc_username, vrc_password, None)
        res = vrchat.get_current_user()
        assert res is not None

        res = vrchat.get_friends(res, datetime.datetime.now())
        assert len(res) > 0