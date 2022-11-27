# Introduction
VRChat で気軽に行われるフレンド申請。  
ダンバー数は容易に超過し、誰が誰だか分からなくなることは有りませんか。

このアプリは AWS 上で VRChat 上のフレンドリストをチェックしフレンド増減を検知。同時に VRChat を動かすPCからもゲームのログをアップする事で相手と何時何処でフレンドになったかを Notion へデータベース形式で自動記録できます。

定期的に記録を見直し、どんな人だったかメモを追記すると不意に遭遇し話しかけられても安心。ついでによく絡むフレンドの誕生日なども記入すると良いかもしれない。

# Installation
## 1. Requirements
AWS CLI がセットアップ済み。Notion にフレンドリスト出力用のデータベース、APIキーが作成済みである事。

| Column              | Type   |
| ------------------- | ------ |
| user_name           | Key    |
| user_name_displayed | String |
| user_id             | String |
| location            | String |
| regist_date         | Date   |
| update_date         | Date   |
| removed_date        | Date   |
| memo                | String |

## 2. Deploy
`dev` の箇所は適宜置き換え可能。

1. CodeCommit にリポジトリを作成し、このリポジトリをプッシュ
2. 開発環境を構築
   * Share/Common/.env を作成
     1. Share/Common/.env.sample をコピーし同階層に作成
     2. 変数部分を埋める
3. インフラを構築
   * deploy_dev_base.sh を作成
     1. AWS_CloudFormation/src/deploy_dev_base_sample.sh をコピーし同階層に作成
     2. 変数部分を埋める
     3. 実行
4. CodeBuild のプロジェクトをビルド
   * vrcu-dev-FriendListMonitor-Dispatcher-codebuild
   * vrcu-dev-FriendListMonitor-Worker-codebuild
   * vrcu-dev-FriendListProcesser-codebuild

## 3. Configure

```bash
Share/Common/.env
# 1. VSCode で Desktop/Admin を開き、ビルド (Ctrl+Shift+B)
# 2. AppDB へ必要情報を登録
python dist/vrcu.pyz account connect_vrchat \
    --account "{MY_VRCHAT_USERID (etc: usr_～))}" \
    --app_table "vrcu-dev-FriendListMonitor-dynamodb" \
    --user_name "{VRCHAT_LOGIN_USERNAME}" \
    --passwd "{VRCHAT_LOGIN_PASSWD}"

python dist/vrcu.pyz account connect_notion \
    --account "{MY_VRCHAT_USERID (etc: usr_～))}" \
    --app_table "vrcu-dev-FriendListMonitor-dynamodb" \
    --auth_token "{NOTION_AUTH_TOKEN}" \
    --friendlist_dbid "{NOTION_DBID}"

# 3. VSCode で Desktop/EventExtractor を開く
# 4. config/setting_sample.ini をコピーし setting.ini を作成。開いて仮置き部分を記入.
#    [profile.sample] セクションの sample 箇所を書き換えて複数定義も可能
# 5. 必要パッケージをインストール
poetry install --no-root

```

# Usage

```bash
# VRChat を起動した後に Desktop/EventExtractor を起動して使用
# --profile {PROFILE_NAME} を通して setting.ini の
# 指定した [profile.{PROFILE_NAME}] セクションを選択できます。
poetry run python src/main.py --profile sample --watch
```