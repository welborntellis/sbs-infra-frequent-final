#! /bin/bash

DEPLOY_TO=$1

source ./Common/PYTHONPATH.sh

echo "--- Upload files to S3"
python Common/s3_helper.py $DEPLOY_TO SbS-cloudwatch-event

echo "--- Creating SbS notification cloudwatch rule Function"
python SbS-cloudwatch-event/sbs_cloudwatch_event_rule.py $DEPLOY_TO sbs_pipeline_batch_notify_event
