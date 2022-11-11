import boto3
import itertools
import json
import logging
import os
import datetime

logger = logging.getLogger(__name__)


class App:
    def __init__(self, target_repo_name: str, target_ref: str, proj2pattern: dict[str, str]):
        self.target_repo_name = target_repo_name
        self.target_ref = target_ref
        self.proj2pattern = proj2pattern
        self.codecommit = boto3.client("codecommit")
        self.codebuild = boto3.client("codebuild")

    def has_modified(self, commit_id_old: str, commit_id_new: str, path_pattern: str) -> bool:
        # 最新の成功ビルドから最新コミットの間の差分を抽出
        api_res = self.debug(
            "has_modified", "get_differences",
            self.codecommit.get_differences(
                repositoryName=self.target_repo_name,
                beforeCommitSpecifier=commit_id_old,
                afterCommitSpecifier=commit_id_new
            )
        )

        diffs = api_res["differences"]
        files = \
            [blb["beforeBlob"]["path"] for blb in diffs if "beforeBlob" in blb] + \
            [blb["afterBlob"]["path"] for blb in diffs if "afterBlob" in blb]
        files = list(sorted(set(files)))
        logger.info("has_modified: 差分の有るファイルを取得\n... {0}".format("\n... ".join(files)))

        res = any(file[:len(path_pattern)] == path_pattern for file in files)
        return res

    def get_commit_of_last_success_deploy(self, buld_project_name: str) -> str:
        # 対象ビルドプロジェクトのビルド履歴を取得
        paginator = self.codebuild.get_paginator("list_builds_for_project")
        build_his = itertools.chain(
            self.debug("get_commit_of_last_success_deploy", "batch_get_builds", api_res_b)
            for api_res_a in paginator.paginate(projectName=buld_project_name, sortOrder="DESCENDING")
            for api_res_b in self.codebuild.batch_get_builds(
                ids=self.debug("get_commit_of_last_success_deploy", "list_builds_for_project", api_res_a)["ids"])["builds"]
            if api_res_b["buildComplete"] and api_res_b["buildStatus"] == "SUCCEEDED"
        )

        # 最新の成功ビルドの情報を取得
        # デプロイ済みのバージョンが無ければフルデプロイ
        try:
            latest_success_build = next(build_his)
            commit_id_old = latest_success_build["resolvedSourceVersion"]
            return commit_id_old
        except StopIteration:
            return None

    def invoke(self, event):
        detail = self.debug("invoke", "event", event)["detail"]
        if detail["repositoryName"] != self.target_repo_name:
            return
        if detail["referenceFullName"] != self.target_ref:
            return
        if detail["event"] != "referenceUpdated":
            return

        project_names = set()
        commit_id_new = detail["commitId"]
        logger.info(f"invoke: 最新のリビジョンを取得 ({commit_id_new})")
        for buld_project_name, path_pattern in self.proj2pattern.items():
            # 最新の成功ビルドの情報を取得
            commit_id_old = self.get_commit_of_last_success_deploy(buld_project_name)
            logger.info(f"invoke: デプロイ済みのリビジョンを取得 ({buld_project_name=}, {commit_id_old=})")
            # 最新の成功ビルドから最新コミットの間の差分を抽出
            if commit_id_old is None or self.has_modified(commit_id_old, commit_id_new, path_pattern):
                project_names.add(buld_project_name)

        logger.info(f"invoke: ビルド処理を開始 ({project_names=})")
        for buld_project_name in project_names:
            self.codebuild.start_build(projectName=buld_project_name)

    @staticmethod
    def debug(method_name: str, variable_name: str, value: dict[str, object]) -> dict[str, object]:
        txt = json.dumps(value, indent=2, default=App.json_enc)
        txt = "\n".join([f"... {line}" for line in txt.splitlines()])
        logger.debug(f"{method_name}: {variable_name}=\n{txt}")
        return value

    @staticmethod
    def json_enc(o):
        if isinstance(o, datetime.datetime):
            return o.isoformat()
        else:
            return o


def lambda_handler(event, context):
    ENV_TYPE = os.getenv("ENV_TYPE")
    LOG_LEVEL = int(os.getenv("LOG_LEVEL", logging.INFO))
    APP_REPOSITORY_NAME = os.getenv("APP_REPOSITORY_NAME")
    APP_REPOSITORY_REF = os.getenv("APP_REPOSITORY_REF")

    logger.setLevel(LOG_LEVEL)
    ssm_client = boto3.client("ssm")
    build_projs = f"/vrcu/{ENV_TYPE}/build-project-mapping/"
    build_projs = ssm_client.get_parameters_by_path(Path=build_projs)
    build_projs = {
        os.path.basename(item["Name"]): item["Value"] for item in build_projs["Parameters"]
    }
    app = App(APP_REPOSITORY_NAME, APP_REPOSITORY_REF, build_projs)
    app.invoke(event)
