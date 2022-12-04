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

        res01 = vrchat.get_current_user()
        assert res01 is not None

        vrc_userid_sample = os.getenv("VRCHAT_USERID_SAMPLE")
        res02 = vrchat.get_user(vrc_userid_sample, datetime.datetime.now())
        assert res02 is not None
        
        res03 = vrchat.get_friends(res01, datetime.datetime.now())
        assert len(res03) > 0
