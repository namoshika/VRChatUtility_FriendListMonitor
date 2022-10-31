import json
import sys
import os

# テスト対象
sys.path.append("src")
import src.lambda_function


def test_handler_name():
    user_id = os.getenv("USER_ID")
    events = {"Records": [{"body": json.dumps({"user_id": user_id})}]}
    src.lambda_function.lambda_handler(events, None)
