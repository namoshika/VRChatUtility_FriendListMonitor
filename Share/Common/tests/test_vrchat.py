import datetime
import os
import sys


class TestService:
    def test_api(self):
        sys.path.append("src")
        import src.vrchat

        vrc_username = os.getenv("VRCHAT_USERNAME")
        vrc_password = os.getenv("VRCHAT_PASSWORD")
        vrchat = src.vrchat.Service(vrc_username, vrc_password, None)
        res = vrchat.get_current_user()
        assert res is not None

        res = vrchat.get_friends(res, datetime.datetime.now())
        assert len(res) > 0