#! /bin/bash

DEPLOY_TO=$1

echo "--- Creating SbS notification Lambda Function"

cd "$( dirname "${BASH_SOURCE[0]}" )"
TEMP_ENV=$(mktemp -d)
python -m venv $TEMP_ENV
. $TEMP_ENV/bin/activate
pip install --no-cache-dir --upgrade pip
pip install --no-cache-dir -r requirements.txt

if ! zappa update --disable_progress "$DEPLOY_TO"; then
    zappa deploy --disable_progress "$DEPLOY_TO"
fi

deactivate

rm -r $TEMP_ENV