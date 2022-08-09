import json
import os
import src.lambda_function


def test_handler_name():
    events = {"Records": [{"body": json.dumps({"user_id": os.getenv("USER_ID")})}]}
    src.lambda_function.lambda_handler(events, None)
