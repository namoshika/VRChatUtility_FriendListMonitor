import json
import sys
import os
from datetime import datetime
from pytest_mock import MockerFixture

sys.path.append("src")


class TestApp:
    def test_invoke(self, mocker: MockerFixture):
        import src.lambda_function

        friend_1 = src.lambda_function.entity.UserInfo("user_id_1", "user_name_1", "user_display_name_1", 0, 0)
        friend_2 = src.lambda_function.entity.UserInfo("user_id_2", "user_name_2", "user_display_name_2", 0, 0)
        friend_3 = src.lambda_function.entity.UserInfo("user_id_3", "user_name_3", "user_display_name_3", 0, 0)

        # ---------------------------
        # Define Mock: dynamodb.Service
        # ---------------------------
        MockDyn = mocker.patch("src.common.dynamodb.Service")
        mock_dyn = MockDyn()
        # vrchat.Service.get_current_user
        mock_dyn_get_friends = mock_dyn.get_friends
        mock_dyn_get_friends.return_value = [friend_1, friend_2]
        # vrchat.Service.put_friend
        mock_dyn_put_friend = mock_dyn.put_friend

        # ---------------------------
        # Define Mock: sqs.ProcesserService
        # ---------------------------
        MockSqs = mocker.patch("src.common.sqs.ProcesserService")
        mock_sqs = MockSqs()
        # vrchat.ProcesserService.enqueue
        mock_sqs_enqueue = mock_sqs.enqueue

        # ---------------------------
        # Define Mock: vrchat.Service
        # ---------------------------
        MockVrc = mocker.patch("src.common.vrchat.Service")
        mock_vrc = MockVrc()
        # vrchat.Service.get_current_user
        mock_get_current_user = mock_vrc.get_current_user
        mock_get_current_user.return_value = {"id": "user_id"}
        # vrchat.Service.get_friends
        mock_get_friends = mock_vrc.get_friends
        mock_get_friends.return_value = [friend_1, friend_3]

        # ---------------------------
        # Test
        # ---------------------------
        vrc = src.common.vrchat.Service()
        dyn = src.common.dynamodb.Service()
        sqs = src.common.sqs.ProcesserService()

        update_date = datetime(2022, 11, 6, 12, 34, 56)
        target = src.lambda_function.App(vrc, dyn, sqs)
        target.invoke(update_date)

        assert mock_sqs_enqueue.call_count == 2
        sqs_arg_op, = mock_sqs_enqueue.call_args_list[0].args
        assert isinstance(sqs_arg_op, src.lambda_function.entity.OperationInfo)
        sqs_arg_op, = mock_sqs_enqueue.call_args_list[1].args
        assert isinstance(sqs_arg_op, src.lambda_function.entity.OperationInfo)

        assert mock_dyn_put_friend.call_count == 2
        sqs_arg_op, = mock_dyn_put_friend.call_args_list[0].args
        assert isinstance(sqs_arg_op, src.lambda_function.entity.OperationInfo)
        sqs_arg_op, = mock_dyn_put_friend.call_args_list[1].args
        assert isinstance(sqs_arg_op, src.lambda_function.entity.OperationInfo)


def test_extract_change_friends():
    import src.lambda_function
    from src.lambda_function import entity

    dat_old = datetime(2022, 11, 4, 12, 34, 56)
    inf_old = [
        entity.UserInfo("user_id_1", "user_name_1", "user_display_name_1", None, dat_old),
        entity.UserInfo("user_id_2", "user_name_2", "user_display_name_2", None, dat_old),
        entity.UserInfo("user_id_3", "user_name_3", "user_display_name_3", None, dat_old),
    ]
    dat_new = datetime(2022, 11, 5, 12, 34, 56)
    inf_new = [
        entity.UserInfo("user_id_1", "user_name_1", "user_display_name_1", None, dat_new),
        entity.UserInfo("user_id_2", "user_name_2 (更新)", "user_display_name_2 (更新)", None, dat_new),
        entity.UserInfo("user_id_4", "user_name_4", "user_display_name_4", None, dat_new),
    ]

    dat_upd = datetime(2022, 11, 6, 12, 34, 56)
    ops = list(src.lambda_function.extract_change_friends(inf_old, inf_new, dat_upd))

    # 更新
    op = ops[0]
    assert op.action == entity.ActionType.UPDATE
    assert op.info_old == inf_old[1]
    assert op.info_new == inf_new[1]

    # 削除
    op = ops[1]
    assert op.action == entity.ActionType.REMOVE
    assert op.info_old == inf_old[2]
    assert op.info_new is None

    # 追加
    op = ops[2]
    assert op.action == entity.ActionType.ADD
    assert op.info_old is None
    assert op.info_new == inf_new[2]

    # --------------------
    # EdgeCase (完全削除)
    # --------------------
    dat_old = datetime(2022, 11, 4, 12, 34, 56)
    inf_old = [
        entity.UserInfo("user_id_1", "user_name_1", "user_display_name_1", None, dat_old),
        entity.UserInfo("user_id_2", "user_name_2", "user_display_name_2", None, dat_old),
    ]
    inf_new = []

    dat_upd = datetime(2022, 11, 6, 12, 34, 56)
    ops = list(src.lambda_function.extract_change_friends(inf_old, inf_new, dat_upd))

    op = ops[0]
    assert op.action == entity.ActionType.REMOVE
    assert op.info_old == inf_old[0]
    assert op.info_new is None

    op = ops[1]
    assert op.action == entity.ActionType.REMOVE
    assert op.info_old == inf_old[1]
    assert op.info_new is None

    # --------------------
    # EdgeCase (完全新規)
    # --------------------
    dat_old = datetime(2022, 11, 4, 12, 34, 56)
    dat_new = datetime(2022, 11, 5, 12, 34, 56)
    inf_old = []
    inf_new = [
        entity.UserInfo("user_id_1", "user_name_1", "user_display_name_1", None, dat_old),
        entity.UserInfo("user_id_2", "user_name_2", "user_display_name_2", None, dat_old),
    ]

    dat_upd = datetime(2022, 11, 6, 12, 34, 56)
    ops = list(src.lambda_function.extract_change_friends(inf_old, inf_new, dat_upd))

    op = ops[0]
    assert op.action == entity.ActionType.ADD
    assert op.info_old is None
    assert op.info_new == inf_new[0]

    op = ops[1]
    assert op.action == entity.ActionType.ADD
    assert op.info_old is None
    assert op.info_new == inf_new[1]

    # --------------------
    # EdgeCase (空)
    # --------------------
    dat_old = datetime(2022, 11, 4, 12, 34, 56)
    dat_new = datetime(2022, 11, 5, 12, 34, 56)
    inf_old = []
    inf_new = []

    dat_upd = datetime(2022, 11, 6, 12, 34, 56)
    ops = list(src.lambda_function.extract_change_friends(inf_old, inf_new, dat_upd))

    assert len(ops) == 0


def test_handler_name():
    import src.lambda_function

    account_id = os.getenv("ACCOUNT_ID")
    events = {"Records": [{"body": json.dumps({"account_id": account_id})}]}
    src.lambda_function.lambda_handler(events, None)
