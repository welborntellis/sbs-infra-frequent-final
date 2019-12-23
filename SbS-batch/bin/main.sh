#! /bin/bash

DEPLOY_TO=$1
FORCE_RECREATE_COMPENV=$2
FORCE_NEW_JOBDEF=$3
START_DIR="$PWD"

source ./Common/PYTHONPATH.sh

echo "--- Upload files to S3"
python Common/s3_helper.py $DEPLOY_TO SbS-batch

echo "--- Creating AWS Batch components"
python SbS-batch/sbs_pipelines_batch.py $DEPLOY_TO $FORCE_RECREATE_COMPENV $FORCE_NEW_JOBDEF
