#!/usr/bin/python3.6
import os
import sys
import time

import boto3
import click

from Common.Config import Config

client = boto3.client('batch', region_name='us-east-1')
env = None
config = None

main_job_queue_name = ''
quick_job_queue_name = ''
recal_job_queue_name = ''


def read_config():
    global config
    global main_job_queue_name
    global quick_job_queue_name
    global recal_job_queue_name

    cfg_file_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                'config',
                                'sbs_config.{}.json'.format(env))

    try:
        config = Config().get_config(cfg_file_path)

        main_job_queue_name = env + config['sbs_pipeline_batch_queue_main_name']
        quick_job_queue_name = env + config[
            'sbs_pipeline_batch_queue_quick_stack_name']
        recal_job_queue_name = env + config[
            'sbs_pipeline_batch_queue_recal_stack_name']
    except Exception as e:
        print('Failed reading config file with error {}'.format(e))
        sys.exit(e)


##########################################################################
# COMPUTE ENVIRONMENT
##########################################################################

def is_comp_env_exists(compute_env_name):
    response = client.describe_compute_environments(
        computeEnvironments=[
            compute_env_name
        ],
    )
    existing_comp_env_name = ""
    compute_env = response['computeEnvironments']
    for x in compute_env:
        existing_comp_env_name = x["computeEnvironmentName"]

    if compute_env_name == existing_comp_env_name:
        print("Compute environment {} exist".format(compute_env_name))
        return True
    else:
        return False


def create_compute_environment(compute_env_name, min_vcpus, max_vcpus, instance_type):
    print("Creating compute environment: {}".format(compute_env_name))
    
    ssm_client = boto3.client('ssm', region_name='us-east-1')
    image_id_response = ssm_client.get_parameter(Name=config['sbs_pipeline_batch_comp_env_image_id_ssm_path'])
    image_id = image_id_response['Parameter']['Value']

    try:
        client.create_compute_environment(
            computeEnvironmentName=compute_env_name,
            type='MANAGED',
            state='ENABLED',
            computeResources={
                'type': 'EC2',
                'minvCpus': min_vcpus,
                'maxvCpus': max_vcpus,
                'imageId': image_id,
                'instanceTypes': [
                    instance_type,
                ],
                'subnets': config['sbs_pipeline_batch_comp_env_subnets'],
                'securityGroupIds': config[
                    'sbs_pipeline_batch_comp_env_sgs'],
                'ec2KeyPair': config['sbs_pipeline_batch_comp_env_keypair'],
                'instanceRole':
                    config['sbs_pipeline_batch_comp_env_instance_role'],
                'tags': {
                    'Name': compute_env_name,
                    'Project': 'thes',
                    'ResourceOwner': 'matt.king@pioneer.com',
                    'DeployedBy': 'ryand.smith@pioneer.com',
                    'Scheduled': 'no'
                },
            },
            serviceRole=config['sbs_pipeline_batch_comp_env_service_role']
        )
        print("Compute environment {} created successfully."
              .format(compute_env_name))
        time.sleep(60)
    except Exception as e:
        print("Failed creating batch compute environment with error {}"
              .format(str(e)))
        sys.exit(e)


def delete_comp_env(comp_env_name):
    print("Deleting compute environment [{}]...".format(comp_env_name))
    client.delete_compute_environment(computeEnvironment=comp_env_name)
    time.sleep(10)


def disable_compute_environment(comp_env_name):
    print("Disabling compute environment [{}]...".format(comp_env_name))
    client.update_compute_environment(
        computeEnvironment=comp_env_name,
        state='DISABLED',
    )
    time.sleep(5)


def wait_till_ce_delete(computeenv):
    try:
        if is_comp_env_exists(computeenv):
            time.sleep(5)
            wait_till_ce_delete(computeenv)
    except Exception as e:
        print('Stack deleted successfully'.format(e))


def verify_and_create_batch_compute_env(create_new, compute_env_name, min_vcpus,
                                        max_vcpus, instance_type):
    if is_comp_env_exists(compute_env_name):
        print("Create compute environment flag set to [{}]".format(create_new))
        if create_new:
            job_qs = [main_job_queue_name, quick_job_queue_name,
                      recal_job_queue_name]
            for q in job_qs:
                if is_job_q_exists(q):
                    disable_jobq(q)
                    delete_jobq(q)
                    wait_till_jobq_delete(q)
            disable_compute_environment(compute_env_name)
            delete_comp_env(compute_env_name)
            wait_till_ce_delete(compute_env_name)
            create_compute_environment(compute_env_name, min_vcpus, max_vcpus, instance_type)
    else:
        create_compute_environment(compute_env_name, min_vcpus, max_vcpus, instance_type)

    return compute_env_name


##########################################################################
# JOB QUEUE
##########################################################################

def is_job_q_exists(job_queue_name):
    response = client.describe_job_queues(
        jobQueues=[
            job_queue_name
        ],
    )
    existing_job_q_name = ""
    job_qs = response["jobQueues"]
    for job_q in job_qs:
        existing_job_q_name = (job_q["jobQueueName"])

    if job_queue_name == existing_job_q_name:
        return True
    else:
        return False


def create_job_queue(job_queue_name, compute_env_name, priority):
    try:
        client.create_job_queue(
            jobQueueName=job_queue_name,
            state='ENABLED',
            priority=priority,
            computeEnvironmentOrder=[
                {
                    'order': 1,
                    'computeEnvironment': compute_env_name,
                },
            ]
        )
    except Exception as e:
        print('Failed creating job queue with error {}'.format(e))
        sys.exit(e)


def disable_jobq(jobq):
    print("Disabling Job Queue [{}].".format(jobq))
    client.update_job_queue(
        jobQueue=jobq,
        state='DISABLED',
    )
    time.sleep(5)


def delete_jobq(jobq):
    print("Deleting Job Queue [{}].".format(jobq))
    client.delete_job_queue(
        jobQueue=jobq
    )
    time.sleep(5)


def wait_till_jobq_delete(jobq):
    try:
        if is_job_q_exists(jobq):
            time.sleep(5)
            wait_till_jobq_delete(jobq)
    except Exception as e:
        print('Job queue deleted successfully'.format(e))


def verify_and_create_batch_job_main_queue(compute_env_name):
    priority = config['sbs_pipeline_batch_queue_main_priority']
    verify_and_create_batch_job_queue(main_job_queue_name, compute_env_name,
                                      priority)


def verify_and_create_batch_job_quick_queue(compute_env_name):
    priority = config['sbs_pipeline_batch_queue_quick_priority']
    verify_and_create_batch_job_queue(quick_job_queue_name, compute_env_name,
                                      priority)


def verify_and_create_batch_job_sbs_recal_queue(compute_env_name):
    priority = config['sbs_pipeline_batch_queue_recal_priority']
    verify_and_create_batch_job_queue(recal_job_queue_name, compute_env_name,
                                      priority)


def verify_and_create_batch_job_queue(job_queue_name, compute_env_name,
                                      priority):
    if is_job_q_exists(job_queue_name):
        print("Job Queue {} exists.".format(job_queue_name))
    else:
        print("Creating Job Queue: {}".format(job_queue_name))
        create_job_queue(job_queue_name, compute_env_name, priority)
        print("Job Queue {} created successfully.".format(job_queue_name))


##########################################################################
# JOB DEFINITION
##########################################################################

def get_job_definition(job_def_name, version):
    response = client.describe_job_definitions(
        jobDefinitions=[
            job_def_name + ":" + str(version)
        ],
        status='ACTIVE',
    )

    return response


def register_job_definition(job_def_name, image_link, vcpus, memory):
    try:
        client.register_job_definition(
            jobDefinitionName=job_def_name,
            type='container',
            containerProperties={
                'image': image_link,
                'vcpus': vcpus,
                'memory': memory,
                'jobRoleArn': config['sbs_pipeline_batch_jobdef_role_arn'],
            },
            retryStrategy={
                'attempts': 1
            }
        )
    except Exception as e:
        print('Failed registering job definition with error {}'.format(e))
        sys.exit(e)

def deregister_job_definition(job_def_name, revision):
    try:
        client.deregister_job_definition(jobDefinition=f"{job_def_name}:{revision}")
    except Exception as e:
        print('Failed deregistering job definition with error {}'.format(e))
        sys.exit(e)


def verify_and_register_batch_rt_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_rt_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_rt_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_rt_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_wt_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_wt_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_wt_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_wt_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_je_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_je_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_je_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_je_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_ic_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_ic_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_ic_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_ic_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_gd_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_gd_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_gd_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_gd_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_dd_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_dd_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_dd_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_dd_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_bl_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_bl_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_bl_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_bl_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_om_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_om_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_om_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_om_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_ps_job_definition(force_job_definition=False):
    job_def_name = env + config['sbs_pipeline_batch_ps_jobdef_name']
    vcpus = int(config['sbs_pipeline_batch_ps_jobdef_vcpus'])
    memory = int(config['sbs_pipeline_batch_ps_jobdef_memory'])
    verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition)


def verify_and_register_batch_job_definition(job_def_name, vcpus, memory, force_job_definition=False):
    print('verifying Job definitions: {}'.format(job_def_name))

    image_link = config['sbs_algorithm_image_name']
    version = 0

    while True:
        version = version + 1

        response = get_job_definition(job_def_name, version)

        job_def_status = ""
        for job_def in response["jobDefinitions"]:
            job_def_status = job_def["status"]

        if job_def_status == "ACTIVE":
            print("Job Definition exists with ACTIVE state")
            if force_job_definition:
                print("De-registering job definition")
                deregister_job_definition(job_def_name, version)
            else:
                break
        elif job_def_status == "INACTIVE":
            print("Job Definition exists with INACTIVE state")
        else:
            print("Creating new job definition")
            register_job_definition(job_def_name, image_link, vcpus, memory)
            print("Job definition {} created successfully".format(job_def_name))
            break


##########################################################################
# Main
##########################################################################

@click.command()
@click.argument('environment')
@click.option('--force', is_flag=True, help="Force creation of a new compute environment even if one already exists.")
@click.option('--force-job-definition', is_flag=True, help="Force creation of a new job definition even if one already exists.")
def main(environment, force, force_job_definition):
    global env
    env = environment
    
    read_config()

    ce_name = env + config['sbs_pipeline_batch_comp_env_name']
    min_vcpus = int(config['sbs_pipeline_batch_comp_env_min_vcpus'])
    max_vcpus = int(config['sbs_pipeline_batch_comp_env_max_vcpus'])
    instance_type = config['sbs_pipeline_batch_comp_env_instance_type']
    verify_and_create_batch_compute_env(force, ce_name,
                                        min_vcpus, max_vcpus, instance_type)

    ce_quick_name = env + config['sbs_pipeline_batch_quick_comp_env_name']
    min_vcpus = int(config['sbs_pipeline_batch_quick_comp_env_min_vcpus'])
    max_vcpus = int(config['sbs_pipeline_batch_quick_comp_env_max_vcpus'])
    instance_type = config['sbs_pipeline_batch_quick_comp_env_instance_type']
    verify_and_create_batch_compute_env(force, ce_quick_name,
                                        min_vcpus, max_vcpus, instance_type)

    verify_and_create_batch_job_main_queue(ce_name)
    verify_and_create_batch_job_quick_queue(ce_quick_name)
    verify_and_create_batch_job_sbs_recal_queue(ce_quick_name)

    verify_and_register_batch_rt_job_definition(force_job_definition)
    verify_and_register_batch_wt_job_definition(force_job_definition)
    verify_and_register_batch_je_job_definition(force_job_definition)
    verify_and_register_batch_ic_job_definition(force_job_definition)
    verify_and_register_batch_gd_job_definition(force_job_definition)
    verify_and_register_batch_dd_job_definition(force_job_definition)
    verify_and_register_batch_bl_job_definition(force_job_definition)
    verify_and_register_batch_om_job_definition(force_job_definition)
    verify_and_register_batch_ps_job_definition(force_job_definition)

    print("Finished setting up SbS Pipeline Batch Environment.")


if __name__ == '__main__':
    main()
