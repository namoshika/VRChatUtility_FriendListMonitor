import os
import src.lambda_function


def test_handler_name():
    src.lambda_function.lambda_handler(None, None)
