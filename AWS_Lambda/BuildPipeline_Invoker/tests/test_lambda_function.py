from asyncio.log import logger
import logging
import os
import src.lambda_function
from pytest_mock.plugin import MockerFixture

handler = logging.FileHandler("log/test.log")
handler.setLevel(logging.DEBUG)
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

class TestAppUt:
    def setup(self):
        os.environ["ENV_TYPE"] = "dev"
        os.environ["LOG_LEVEL"] = str(logging.DEBUG)

    def test_has_modified(self, mocker: MockerFixture):
        mock_client = mocker.patch("boto3.client")
        mock_client("codecommit").get_differences.return_value = {
            "differences": [
                {
                    "beforeBlob": {
                        "blobId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        "path": "path_pattern1/lambda_function.py",
                        "mode": "999999"
                    },
                    "afterBlob": {
                        "blobId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        "path": "path_pattern1/lambda_function.py",
                        "mode": "999999"
                    },
                    "changeType": "M"
                },
                {
                    "afterBlob": {
                        "blobId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        "path": "path_pattern2/lambda_function.py",
                        "mode": "999999"
                    },
                    "changeType": "A"
                },
                {
                    "beforeBlob": {
                        "blobId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                        "path": "path_pattern2/lambda_function.py",
                        "mode": "999999"
                    },
                    "changeType": "D"
                }
            ]
        }

        app = src.lambda_function.App(
            "RepositoryName",
            "refs/heads/master",
            {
                "CodeBuildProject1": "path_pattern1/",
                "CodeBuildProject2": "path_pattern2/"
            }
        )
        assert app.has_modified("aaa", "bbb", "path_pattern1/") == True
        assert app.has_modified("aaa", "bbb", "path_pattern3/") == False

    def test_get_commit_of_last_success_deploy_01(self, mocker: MockerFixture):
        mock_client = mocker.patch("boto3.client")
        mock_paginate = mock_client("codebuild") \
            .get_paginator("list_builds_for_project") \
            .paginate
        mock_paginate.return_value = [{"ids": ["aaa", "bbb", "ccc"]}]
        mock_batch_get_builds = mock_client("codebuild").batch_get_builds
        mock_batch_get_builds.return_value = {
            "builds": [
                {
                    "buildComplete": False,
                    "buildStatus": "SUCCEEDED",
                    "resolvedSourceVersion": "commit_id_1"
                },
                {
                    "buildComplete": True,
                    "buildStatus": "Failed",
                    "resolvedSourceVersion": "commit_id_2"
                },
                {
                    "buildComplete": True,
                    "buildStatus": "SUCCEEDED",
                    "resolvedSourceVersion": "commit_id_3"
                },
            ]
        }

        app = src.lambda_function.App(
            "RepositoryName",
            "refs/heads/master",
            {
                "CodeBuildProject1": "path_pattern1/",
                "CodeBuildProject2": "path_pattern2/"
            }
        )
        res = app.get_commit_of_last_success_deploy("CodeBuildProject1")
        assert res == "commit_id_3"

        mock_paginate.assert_called_once_with(
            projectName="CodeBuildProject1", sortOrder="DESCENDING")
        mock_batch_get_builds.assert_called_once_with(ids=["aaa", "bbb", "ccc"])

    def test_get_commit_of_last_success_deploy_02(self, mocker: MockerFixture):
        mock_client = mocker.patch("boto3.client")
        mock_paginate = mock_client("codebuild") \
            .get_paginator("list_builds_for_project") \
            .paginate
        mock_paginate.return_value = [{"ids": ["aaa", "bbb", "ccc"]}]
        mock_batch_get_builds = mock_client("codebuild").batch_get_builds
        mock_batch_get_builds.return_value = {
            "builds": [
                {
                    "buildComplete": False,
                    "buildStatus": "SUCCEEDED",
                    "resolvedSourceVersion": "commit_id_1"
                },
                {
                    "buildComplete": True,
                    "buildStatus": "Failed",
                    "resolvedSourceVersion": "commit_id_2"
                }
            ]
        }

        app = src.lambda_function.App(
            "RepositoryName",
            "refs/heads/master",
            {
                "CodeBuildProject1": "path_pattern1/",
                "CodeBuildProject2": "path_pattern2/"
            }
        )
        res = app.get_commit_of_last_success_deploy("CodeBuildProject1")
        assert res is None

    def test_invoke_01(self, mocker: MockerFixture):
        mock_client = mocker.patch("boto3.client")
        mock_start_build = mock_client("codebuild").start_build
        app = src.lambda_function.App(
            "RepositoryName",
            "refs/heads/master",
            {
                "CodeBuildProject1": "path_pattern1/",
                "CodeBuildProject2": "path_pattern2/"
            }
        )
        mock_func_01 = mocker.patch.object(app, "get_commit_of_last_success_deploy")
        mock_func_01.return_value = "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
        mock_func_02 = mocker.patch.object(app, "has_modified")
        mock_func_02.return_value = True

        event = {
            "version": "0",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "detail-type": "CodeCommit Repository State Change",
            "source": "aws.codecommit",
            "account": "999999999999",
            "time": "20XX-01-23T01:23:45Z",
            "region": "ap-northeast-1",
            "resources": [
                "arn:aws:codecommit:ap-northeast-1:999999999999:RepositoryName"
            ],
            "detail": {
                "callerUserArn": "arn:aws:iam::999999999999:user/USERNAME",
                "commitId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "event": "referenceUpdated",
                "oldCommitId": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
                "referenceFullName": "refs/heads/master",
                "referenceName": "master",
                "referenceType": "branch",
                "repositoryId": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                "repositoryName": "RepositoryName"
            }
        }
        app.invoke(event)

        mock_func_01.assert_any_call("CodeBuildProject1")
        mock_func_02.assert_any_call(
            "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "path_pattern1/")
        mock_func_01.assert_any_call("CodeBuildProject2")
        mock_func_02.assert_any_call(
            "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "path_pattern2/")
        mock_start_build.assert_any_call(projectName="CodeBuildProject1")
        mock_start_build.assert_any_call(projectName="CodeBuildProject2")

    def test_invoke_02(self, mocker: MockerFixture):
        mock_client = mocker.patch("boto3.client")
        mock_start_build = mock_client("codebuild").start_build
        app = src.lambda_function.App(
            "RepositoryName",
            "refs/heads/master",
            {
                "CodeBuildProject1": "path_pattern1/",
                "CodeBuildProject2": "path_pattern2/"
            }
        )
        mock_func_01 = mocker.patch.object(app, "get_commit_of_last_success_deploy")
        mock_func_01.return_value = None
        mock_func_02 = mocker.patch.object(app, "has_modified")
        mock_func_02.return_value = True

        event = {
            "version": "0",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "detail-type": "CodeCommit Repository State Change",
            "source": "aws.codecommit",
            "account": "999999999999",
            "time": "20XX-01-23T01:23:45Z",
            "region": "ap-northeast-1",
            "resources": [
                "arn:aws:codecommit:ap-northeast-1:999999999999:RepositoryName"
            ],
            "detail": {
                "callerUserArn": "arn:aws:iam::999999999999:user/USERNAME",
                "commitId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "event": "referenceUpdated",
                "oldCommitId": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
                "referenceFullName": "refs/heads/master",
                "referenceName": "master",
                "referenceType": "branch",
                "repositoryId": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                "repositoryName": "RepositoryName"
            }
        }
        app.invoke(event)

        mock_func_01.assert_any_call("CodeBuildProject1")
        mock_func_01.assert_any_call("CodeBuildProject2")
        mock_func_02.assert_not_called()
        mock_start_build.assert_any_call(projectName="CodeBuildProject1")
        mock_start_build.assert_any_call(projectName="CodeBuildProject2")

    def test_invoke_03(self, mocker: MockerFixture):
        mock_client = mocker.patch("boto3.client")
        mock_start_build = mock_client("codebuild").start_build
        app = src.lambda_function.App(
            "RepositoryName",
            "refs/heads/master",
            {
                "CodeBuildProject1": "path_pattern1/",
                "CodeBuildProject2": "path_pattern2/"
            }
        )
        mock_func_01 = mocker.patch.object(app, "get_commit_of_last_success_deploy")
        mock_func_01.return_value = "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy"
        mock_func_02 = mocker.patch.object(app, "has_modified")
        mock_func_02.return_value = False

        event = {
            "version": "0",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "detail-type": "CodeCommit Repository State Change",
            "source": "aws.codecommit",
            "account": "999999999999",
            "time": "20XX-01-23T01:23:45Z",
            "region": "ap-northeast-1",
            "resources": [
                "arn:aws:codecommit:ap-northeast-1:999999999999:RepositoryName"
            ],
            "detail": {
                "callerUserArn": "arn:aws:iam::999999999999:user/USERNAME",
                "commitId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "event": "referenceUpdated",
                "oldCommitId": "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
                "referenceFullName": "refs/heads/master",
                "referenceName": "master",
                "referenceType": "branch",
                "repositoryId": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                "repositoryName": "RepositoryName"
            }
        }
        app.invoke(event)

        mock_func_01.assert_any_call("CodeBuildProject1")
        mock_func_02.assert_any_call(
            "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "path_pattern1/")
        mock_func_01.assert_any_call("CodeBuildProject2")
        mock_func_02.assert_any_call(
            "yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy",
            "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", "path_pattern2/")
        mock_start_build.assert_not_called()

    def test_handler_name(self, mocker: MockerFixture):
        mock_app = mocker.patch("src.lambda_function.App")

        os.environ["APP_REPOSITORY_NAME"] = "VRChatUtility_FriendListMonitor"
        os.environ["APP_REPOSITORY_REF"] = "refs/heads/master"
        event = {
            "version": "0",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "detail-type": "CodeCommit Repository State Change",
            "source": "aws.codecommit",
            "account": "999999999999",
            "time": "20XX-01-23T01:23:45Z",
            "region": "ap-northeast-1",
            "resources": [
                "arn:aws:codecommit:ap-northeast-1:999999999999:RepositoryName"
            ],
            "detail": {
                "callerUserArn": "arn:aws:iam::999999999999:user/USERNAME",
                "commitId": "901b01063e4a565a8aa66a958b29a973151e6cd9",
                "event": "referenceUpdated",
                "oldCommitId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "referenceFullName": "refs/heads/master",
                "referenceName": "master",
                "referenceType": "branch",
                "repositoryId": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                "repositoryName": "VRChatUtility_FriendListMonitor"
            }
        }
        src.lambda_function.lambda_handler(event, None)
        mock_app().invoke.assert_any_call(event)


class TestAppIt:
    def setup(self):
        os.environ["ENV_TYPE"] = "dev"
        os.environ["LOG_LEVEL"] = str(logging.DEBUG)

    def test_handler_name(self):
        os.environ["APP_REPOSITORY_NAME"] = "VRChatUtility_FriendListMonitor"
        os.environ["APP_REPOSITORY_REF"] = "refs/heads/master"
        event = {
            "version": "0",
            "id": "ffffffff-ffff-ffff-ffff-ffffffffffff",
            "detail-type": "CodeCommit Repository State Change",
            "source": "aws.codecommit",
            "account": "999999999999",
            "time": "20XX-01-23T01:23:45Z",
            "region": "ap-northeast-1",
            "resources": [
                "arn:aws:codecommit:ap-northeast-1:999999999999:RepositoryName"
            ],
            "detail": {
                "callerUserArn": "arn:aws:iam::999999999999:user/USERNAME",
                "commitId": "901b01063e4a565a8aa66a958b29a973151e6cd9",
                "event": "referenceUpdated",
                "oldCommitId": "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
                "referenceFullName": "refs/heads/master",
                "referenceName": "master",
                "referenceType": "branch",
                "repositoryId": "ffffffff-ffff-ffff-ffff-ffffffffffff",
                "repositoryName": "VRChatUtility_FriendListMonitor"
            }
        }
        src.lambda_function.lambda_handler(event, None)
