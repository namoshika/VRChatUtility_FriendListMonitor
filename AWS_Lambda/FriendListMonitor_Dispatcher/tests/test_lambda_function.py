import sys

sys.path.append("src")


def test_handler_name():
    import src.lambda_function
    src.lambda_function.lambda_handler(None, None)
