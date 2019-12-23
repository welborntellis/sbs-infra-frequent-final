#!/bin/bash

DEPLOY_TO=$1
export AWS_DEFAULT_REGION=us-east-1
DB_URL=$(aws ssm get-parameter --name "/$DEPLOY_TO-thes/sbs/db/url" --output text --query Parameter.Value)
DB_NAME=$(aws ssm get-parameter --name "/$DEPLOY_TO-thes/sbs/db/name" --output text --query Parameter.Value)
DB_USERNAME=$(aws ssm get-parameter --name "/$DEPLOY_TO-thes/sbs/db/username" --output text --query Parameter.Value)
DB_PASSWORD=$(aws ssm get-parameter --with-decryption --name "/$DEPLOY_TO-thes/sbs/db/password" --output text --query Parameter.Value)
DB_DEPLOY_USERNAME=$(aws ssm get-parameter --name "/$DEPLOY_TO-thes/sbs/db/deploy/username" --output text --query Parameter.Value)
DB_DEPLOY_PASSWORD=$(aws ssm get-parameter --with-decryption --name "/$DEPLOY_TO-thes/sbs/db/deploy/password" --output text --query Parameter.Value)


/usr/bin/mysql --defaults-extra-file=SbS-rds-users/config/mysql.conf -h $DB_URL << EOF

GRANT SELECT,INSERT,UPDATE,DELETE ON $DB_NAME.* TO '$DB_USERNAME'@'%' IDENTIFIED BY '$DB_PASSWORD';
GRANT CREATE,CREATE VIEW,ALTER,DROP,SELECT,INSERT,UPDATE,DELETE,INDEX ON $DB_NAME.* TO '$DB_DEPLOY_USERNAME'@'%' IDENTIFIED BY '$DB_DEPLOY_PASSWORD';

EOF