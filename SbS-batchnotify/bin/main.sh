#!/bin/bash
set -e

DEPLOY_TO=$1

echo "ENVIRONMENT IS: $DEPLOY_TO"
echo "Executing SbS-batchnotify/config/$DEPLOY_TO.ini"
stackility upsert -i SbS-batchnotify/config/$DEPLOY_TO.ini