DEPLOY_TO=$1

echo "--- Creating SbS RDS Database users to env: $DEPLOY_TO"
bash ./SbS-rds-users/bin/create_db_users.sh $DEPLOY_TO