import json
import os
import datetime
import boto3
from dateutil import parser
import requests
from azure_oidc_auth import AzureOIDCAuth
print("Starting batch notify lambda............")
print('Theseus SbS Batch SNS notification...')

STATUS_RUNNING = "RUNNING"
STATUS_STOPPED = "STOPPED"
SNS_TOPIC = os.environ['sbs_pipeline_batch_sns_topic_arn']
SNS_PARSER_TOPIC = os.environ['sbs_pipeline_parser_sns_topic_arn']
SUBJECT = 'SbS {} {}: {}'
TIME_TAKEN_TEXT = 'JOB DURATION: {}'
STATUS_TEXT = 'STATUS: {}'
FAILURE_REASON_TEXT = 'FAILURE REASON: {}'

env = ""
aws_region = os.environ['AWS_REGION']
batch_log_group = os.environ['sbs_batch_log_group']
sender_email = os.environ['sender_email']
support_email = os.environ['destination_email']

print("*************************************")
def send_to_sns(message, context):
    """
    When a Job a submitted to AWS Batch and its in running state it will create
    ECS task, this task state change will trigger this function and send a JSON 
    with status and environment attributes. 
    If the status is RUNNING, it will send a SNS notification as email to SNS
    topic subscribers.
    If the status is STOPPED, this function will check if exit code is 0 or 1, 
    if 1 then its FAILED and this function will fetch the reason from JSON. 
    Then, it will send a SNS notification as email to SNS
    topic subscribers.

    :param message: ECS task State change JSON message 
    :param context: Lambda function context
    """

    print('Event: ' + json.dumps(message))

    # "PENDING", "RUNNING", "STOPPED"
    status = message['detail']['lastStatus']
    container = message['detail']['containers'][0]
    container_override = message['detail']['overrides']['containerOverrides'][0]
    command = container_override['command']
    if not command:
        raise Exception('Failed to get pipeline commands')

    file_path = command[1]
    sample_id, analysis_id = (None, None)
    junction_uuid = 0 # for junction extension pipeline
    new_map_id, map_id = (None, None) # for observed map pipeline

    pipeline_info = {
        "EC2_RoutinePipeline.sh": 'Routine',
        "EC2_PostRoutinePipeline.sh": "Post_Routine",
        "EC2_DuplicationDetection.sh": 'Duplicate_Detection',
        "EC2_GeneDisruption.sh": 'Gene_Disruption',
        "EC2_JunctionExtension.sh": 'Junction_Extension',
        "EC2_EndogenousPipeline.sh": 'Endogenous',
        "EC2_ObservedMapCreate.sh": 'Create_Observed_Map',
        "EC2_ObservedMapUpdate.sh": 'Update_Observed_Map',
        "EC2_Blast.sh": 'Blast',
        "sbs_submit_pipeline.py": 'Pipeline Submit'
    }
    pipeline_name = pipeline_info.get(os.path.basename(file_path))
    if not pipeline_name:
        raise Exception('Failed to get Pipeline name')

    # set parser_input_params
    parser_input_params = {'file_path': file_path, 'pipeline': pipeline_name}

    for idx, cmd in enumerate(command):
        if cmd == "-s":
            parser_input_params['sample_id'] = command[idx + 1]
        if cmd == "-a":
            parser_input_params['analysis_id'] = command[idx + 1]
        if cmd == "--bucket":
            parser_input_params['bucket_name'] = command[idx + 1]
        if cmd == "--junction_uuid":
            parser_input_params['junction_uuid'] = command[idx + 1]
        if cmd == "-n":
            parser_input_params['new_map_id'] = command[idx + 1]
        if cmd == "-m":
            parser_input_params['map_id'] = command[idx + 1]
        if cmd == "--endo_set":
            parser_input_params['endo_set'] = command[idx + 1]
        if pipeline_name == 'Duplicate_Detection':
            if cmd == "-O":
                parser_input_params['request_id'] = command[idx + 1]
            if cmd == "-o":
                parser_input_params['output_file'] = command[idx + 1]
        if pipeline_name == 'Gene_Disruption':
            if cmd == "--outdir":
                parser_input_params['s3_gd_outdir'] = command[idx + 1]
            if cmd == "--organism":
                parser_input_params['organism'] = command[idx + 1]

    parser_body_message = json.dumps(parser_input_params,
                                     sort_keys=True, indent=4,
                                     separators=(',', ': '))

    note = ''
    pipeline_notify_str = "{} [{}]".format(pipeline_name, sample_id)
    # get api url
    global env
    global api_url
    env = parser_input_params['bucket_name'].split("-")[0]
    api_parameter = get_ssm_parameters(api_url=f"/{env}-thes/sbs/api_url")
    api_url = api_parameter['api_url']+"/sbs"

    body_msg = json.dumps(container_override,
                          sort_keys=True,
                          indent=4,
                          separators=(',', ': '))

    if status == STATUS_RUNNING:
        STATUS_TEXT.format(status)
        note = {"topic": SNS_TOPIC,
                "subject": SUBJECT.format(env, status, pipeline_notify_str),
                "body": STATUS_TEXT.format(status) + '\n\n' + body_msg}

    elif status == STATUS_STOPPED:
        time_taken = ''
        if 'startedAt' in message['detail'] \
                and 'stoppedAt' in message['detail'] :
            started_at = message['detail']['startedAt']
            stopped_at = message['detail']['stoppedAt']

            started_at_dt = parser.parse(started_at)
            stopped_at_dt = parser.parse(stopped_at)

            time_taken = str(stopped_at_dt - started_at_dt)

        container_status = container['lastStatus']
        body = ''
        if container_status == STATUS_STOPPED:
            if container['exitCode'] == 0:
                status = 'SUCCESS'
                body = STATUS_TEXT.format(status) + '\n' \
                       + TIME_TAKEN_TEXT.format(time_taken) + '\n\n' \
                       + body_msg
                # ignore calling parser lambda for Blast and Pipeline Submit pipeline
                ignore_pipelines = ['Blast', 'Pipeline Submit']
                if pipeline_name not in ignore_pipelines:
                    parser_note = {
                        "topic": SNS_PARSER_TOPIC,
                        "subject": SUBJECT.format(env, status, pipeline_notify_str),
                        "body": parser_body_message
                    }
                    publish_to_sns(parser_note)

            elif container['exitCode'] == 1:
                status = 'FAILED'
                job_details = container_override.get('environment')
                job_id, job_queue = (None, None)
                for info in job_details:
                    if info.get('name') == 'AWS_BATCH_JQ_NAME':
                        job_queue = info.get('value')
                    if info.get('name') == 'AWS_BATCH_JOB_ID':
                        job_id = info['value']
                if job_id and job_queue:
                    client_auth = get_authenticator()
                    send_email_and_update_status(job_id, job_queue, client_auth, started_at)
                    return
                failure_reason = container['reason']
                body_msg = json.dumps(container_override,
                                      sort_keys=True,
                                      indent=4,
                                      separators=(',', ': '))
                body = STATUS_TEXT.format(status) + '\n' \
                       + FAILURE_REASON_TEXT.format(failure_reason) + '\n\n' \
                       + TIME_TAKEN_TEXT.format(time_taken) + '\n\n' \
                       + body_msg

        note = {"topic": SNS_TOPIC,
                "subject": SUBJECT.format(env, status, pipeline_notify_str),
                "body": body}

    if note and pipeline_name not in ['Pipeline Submit']:
        publish_to_sns(note)


def publish_to_sns(message):
    # This function receives JSON input with three fields: the ARN of an SNS topic,
    # a string with the subject of the message, and a string with the body of the message.
    # The message is then sent to the SNS topic.
    #
    # Example:
    #   {
    #       "topic": "arn:aws:sns:REGION:123456789012:MySNSTopic",
    #       "subject": "This is the subject of the message.",
    #       "body": "This is the body of the message."
    #   }

    sns = boto3.client('sns')
    sns.publish(
        TopicArn=message['topic'],
        Subject=message['subject'],
        Message=message['body']
    )

    return 'Sent a message to an Amazon SNS topic.'


def get_log_link(log_group_name, log_stream_name, started_at):
    if log_group_name and log_stream_name:
        log_link = f"https://console.aws.amazon.com/cloudwatch/home?region={aws_region}" \
            f"#logEventViewer:group={log_group_name};stream={log_stream_name};start={started_at}"
        return log_link


def email_support(error_txt, log_stream_name, startedAt):
    if os.environ.get("SKIP_EMAIL") == "True":
        return

    msg_body = "The following error occurred while executing SbS Pipeline:\n\n"
    msg_body += error_txt
    log_link = get_log_link(batch_log_group, log_stream_name, startedAt)
    if log_link:
        msg_body += "\n\nFull Logs:\n" + log_link

    ses = boto3.client('ses')
    ses.send_email(
        Source=sender_email,
        Destination= {
            'ToAddresses': [support_email]
        },
        Message={
            'Subject': {
                'Data': 'An error occurred while executing SbS Pipeline'
            },
            'Body': {
                'Text': {
                    'Data': msg_body
                }
            }
        }
    )


def get_ssm_parameters(**ssm_paths):
    ssm_client = boto3.client('ssm', region_name=aws_region)
    parameters_response = ssm_client.get_parameters(Names=list(ssm_paths.values()), WithDecryption=True)
    if parameters_response['InvalidParameters']:
        raise Exception("There were invalid parameters: %s", parameters_response['InvalidParameters'])

    parameters = parameters_response['Parameters']
    results = {}
    for ssm_path_key in ssm_paths:
        ssm_path = ssm_paths[ssm_path_key]
        for parameter in parameters:
            if parameter['Name'] == ssm_path:
                results[ssm_path_key] = parameter['Value']

    return results


def get_authenticator():

    ssm_parameters = get_ssm_parameters(tenant_id=f"/{env}-thes/sbs/azure/tenant/id",
                                        client_id=f"/{env}-thes/sbs/azure/client/id",
                                        client_secret=f"/{env}-thes/sbs/azure/client/secret")

    tenant_id = ssm_parameters["tenant_id"]
    client_id = ssm_parameters["client_id"]
    client_secret = ssm_parameters["client_secret"]

    tenant_url = f"https://login.microsoftonline.com/{tenant_id}"
    resource_id = client_id
    auth = AzureOIDCAuth(tenant_url)
    client_auth = auth.client_credentials_auth(resource_id, client_id, client_secret)
    return client_auth


def send_email_and_update_status(job_id, job_queue, auth, startedAt):
    '''
    Get log-stream from DB
    Get text error log
    Send email
    Update job-status DB value to "Error"
    '''       
    job_status_record_endpoint = f"{api_url}/pipelines/job_id/{job_id}/job_queue/{job_queue}/job_status"    
    try:
        job_record_res = requests.get(job_status_record_endpoint, auth=auth)        
        job_record_res.raise_for_status()        
    except Exception as e:
        raise Exception('Error while getting job record: {}'.format(str(e)))

    log_stream = job_record_res.json().get('data').get('log_stream')
    if log_stream:
        job_status_id = job_record_res.json().get('data').get('id')
        job_log_endpoint = f"{api_url}/pipelines/job_logs/{job_status_id}"
        try:
            job_log_res = requests.get(job_log_endpoint, auth=auth)
            job_log_res.raise_for_status()            
        except Exception as e:
            raise Exception('Error while fetching job logs for job_id: {} with error : {}'.format(job_status_id, str(e)))
        
        error_text = job_log_res.json().get('data')
        # send email        
        if error_text:
            try:
                print("started at.................", startedAt)
                email_support(error_text, log_stream, startedAt)
            except Exception as e:
                raise Exception('Error while sending email with error : {}'.format(str(e)))

        # finally update the batch job status to 'Error'
        job_status_upd_endpoint = f"{api_url}/pipelines/job_status/{job_status_id}"
        job_status_params = {'job_status': 'Error'}
        try:
            job_status_res = requests.put(job_status_upd_endpoint, json.dumps(job_status_params), auth=auth)
            job_status_res.raise_for_status()
            print("Job status update Response: {}".format(json.dumps(job_status_res.json(), indent=4)))
        except Exception as e:
            raise Exception('Failed to update job_status with error: {}'.format(str(e)))
