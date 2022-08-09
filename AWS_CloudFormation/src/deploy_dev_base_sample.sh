#!/bin/sh

TMPS3_BUCKET=xxx
TMPS3_PREFIX=xxx
APP_REPO_NAME=xxx
APP_REPO_URL=xxx
APP_REPO_ARN=xxx
APP_REPO_REF=refs/heads/master

aws cloudformation package \
    --s3-bucket $TMPS3_BUCKET \
    --s3-prefix $TMPS3_PREFIX \
    --template-file "src/template_base.yaml" \
    --output-template-file "src/template_base_packaged.yaml"

aws cloudformation deploy \
    --stack-name "vrcu-dev-FriendListMonitor-base" \
    --template-file "src/template_base_packaged.yaml" \
    --capabilities "CAPABILITY_NAMED_IAM" \
    --parameter-overrides \
        EnvType=dev \
        TempS3Bucket=$TMPS3_BUCKET TempS3Prefix=$TMPS3_PREFIX \
        AppRepoName=$APP_REPO_NAME AppRepoUrl=$APP_REPO_URL \
        AppRepoArn=$APP_REPO_ARN AppRepoRef=$APP_REPO_REF