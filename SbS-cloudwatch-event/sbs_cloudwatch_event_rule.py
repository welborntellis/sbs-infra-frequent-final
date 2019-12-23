import os
import sys
import time
from os.path import join

import boto3
import botocore

from Common.Config import Config
from Common.Stack import Stack

env = str(sys.argv[1])
in_event = str(sys.argv[2])

cft_file = 'cft-cloudwatch-event.json'
cft_template = join(os.path.dirname(os.path.abspath(__file__)),
                    cft_file)
cfg_file_path = join(os.path.dirname(os.path.abspath(__file__)),
                     'config',
                     'sbs_config.{}.json'.format(env))

account_id = ''
cloudwatch_event_name = ''
cloudwatch_event_ID = ''
s3_bucket_name = ''
lambdaname = ''
lambdaARN = ''
lambdaId = ''
cfn_role_arn = ''
cft_stack_name = ''
s3_files_path = ''
comp_envs = []
region_name = ''
create_new = False


def read_config():
    config = Config().get_config(cfg_file_path)

    global account_id
    global cfn_role_arn
    global region_name
    global s3_bucket_name
    global s3_files_path

    global cloudwatch_event_name
    global cloudwatch_event_ID
    global lambdaARN
    global lambdaname
    global cft_stack_name
    global comp_envs
    global create_new

    try:
        account_id = config['sbs_account_id']
        s3_files_path = config['sbs_pipeline_s3_files_path']
        region_name = config['sbs_region_name']
        cfn_role_arn = config['sbs_cfn_role_arn']
        s3_bucket_name = config['sbs_s3_bucket']

        event = config[in_event]

        create_new = event['create_new']
        cloudwatch_event_name = env + event['event_name']
        cloudwatch_event_ID = env + event['event_ID']
        lambdaname = env + event['sns_lambda_function_name'] + '-' + env
        cft_stack_name = env + event['event_rule_stack']
        compute_env = event['compute_env']
        comp_envs = []
        for ce in compute_env:
            comp_envs.append(env + ce)
    except Exception as e:
        print('Failed reading config file with error {}'.format(e))
        sys.exit(e)


def get_ecs_cluster_arn(compute_env):
    client = boto3.client('batch', region_name=region_name)
    ecs_cluster_arn = ''
    try:
        response = client.describe_compute_environments(
            computeEnvironments=[
                compute_env
            ]
        )
        ecs_cluster_arn = (response['computeEnvironments'][0]['ecsClusterArn'])

    except Exception as e:
        print(
            "Exception occurred while describing compute environment {}: {}".format(
                compute_env, e))

    return ecs_cluster_arn


def get_lambda_arn():
    lambda_client = boto3.client('lambda', region_name=region_name)
    try:
        notify_lambda = lambda_client.get_function(FunctionName=lambdaname)
        print('Trigger Lambda {} exist'.format(lambdaname))
        return notify_lambda['Configuration']['FunctionArn']
    except botocore.errorfactory.ResourceNotFoundException as err:
        print('Lambda {} does not exist'.format(lambdaname))
        sys.exit(err)


def remove_target():
    print('Removing target {} from rule {}'.format(cloudwatch_event_ID,
                                                   cloudwatch_event_name))
    try:
        client = boto3.client('events', region_name=region_name)
        res = client.remove_targets(
            Rule=cloudwatch_event_name,
            Ids=[
                cloudwatch_event_ID
            ]
        )
        time.sleep(5)
        print('Remove Target response : {}', res)
    except Exception as e:
        print('Exception occurred while removing target: {}'.format(e))


def main():
    read_config()

    timeout = 180

    comp_env_arns = []
    for ce in comp_envs:
        comp_env_arns.append(get_ecs_cluster_arn(ce))

    stack_parameters = [
        {
            'ParameterKey': 'EnvironmentValue',
            'ParameterValue': env
        },
        {
            'ParameterKey': 'ruleName',
            'ParameterValue': cloudwatch_event_name
        },
        {
            'ParameterKey': 'lambdaId',
            'ParameterValue': cloudwatch_event_ID
        },
        {
            'ParameterKey': 'lambdaARN',
            'ParameterValue': get_lambda_arn()
        },
        {
            'ParameterKey': 'batchECSClusterARN',
            'ParameterValue': ','.join(comp_env_arns)
        }
    ]

    template_url = 'https://s3.amazonaws.com/{}/{}/{}' \
        .format(s3_bucket_name, s3_files_path, cft_file)

    stack = Stack(cft_stack_name, cft_template, cfn_role_arn, stack_parameters,
                  template_url=template_url, region_name=region_name,
                  timeout=timeout)

    try:
        stack.validate_cf_template()

        if stack.exist():
            if create_new:
                remove_target()
                stack.delete()
                stack.wait_till_stack_exists()
                stack.create()
                stack.wait_till_stack_create()
                print('Successfully created stack {} for sbs'.format(
                    cft_stack_name))
        else:
            stack.create()
            stack.wait_till_stack_create()
            print(
                'Successfully created stack {} for sbs'.format(cft_stack_name))

    except Exception as e:
        print('Failed creating stack for sbs cloudwatch event: {}'.format(e))
        sys.exit(1)


if __name__ == '__main__':
    main()
