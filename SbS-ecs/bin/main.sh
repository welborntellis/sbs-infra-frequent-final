#! /bin/bash

DEPLOY_TO=$1

source ./Common/PYTHONPATH.sh

echo "--- Creating SbS ecs cluster for fast executing jobs"
stackility upsert -i SbS-ecs/config/$DEPLOY_TO.ini
