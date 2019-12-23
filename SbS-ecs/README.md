Brief description:
 
* Deployed as classic ECS in dsi-sandbox, dsi-non-prod(dv and qa) and dsi-prod
* Scales on queue length:
    * sb queue: https://sqs.us-east-1.amazonaws.com/947682355454/sbs-ecs-batch
    * dv queue: https://sqs.us-east-1.amazonaws.com/820225517789/dv-sbs-ecs-batch
    * qa queue: https://sqs.us-east-1.amazonaws.com/820225517789/qa-sbs-ecs-batch
    * pd queue: https://sqs.us-east-1.amazonaws.com/091853933339/sbs-ecs-batch
* Command executed is configured with SSM parameter, current value for all is /bin/ls:
    * sb parameter: /theseus/sbs/receive_message/command
    * dv parameter: /theseus/sbs/receive_message/command_dv
    * qa parameter: /theseus/sbs/receive_message/command_qa
    * pd parameter: /theseus/sbs/receive_message/command
    * note: the command is read for every message so it can be changed without redeployment
* Example message posted: [ "/bin" ] sent to the queue will execute the configured command with those arguments (e.g.: /bin/ls /bin).
* CloudWatch logs can be found in:
    * sb logs group: ECSLogGroup-sbs-ecs-batch-cluster
    * dv logs group: ECSLogGroup-dv-sbs-ecs-batch-cluster
    * qa logs group: ECSLogGroup-qa-sbs-ecs-batch-cluster
    * pd logs group: ECSLogGroup-sbs-ecs-batch-cluster
* There are two Docker images base and SQS reader
    * The image for the base is created with ```base-image/Dockerfile```
    * The image for the SQS reader is created with ```sqs-reader-image/Dockerfile```
    * The images are built with ```code_pipeline/build_image.sh```
* CodePipeline can be viewed here: https://console.aws.amazon.com/codepipeline/home?region=us-east-1#/view/SbS-batch-pipeline
* The ECS and associated bits are (for now): https://bitbucket.phibred.com/users/takledu/repos/sbs-batch-work/browse
* The CodePipeline is here: https://bitbucket.phibred.com/users/takledu/repos/aws_pipelines/browse
* The cluster arn is exported as <env>-thes-sbs-ecs-batch-cluster-arn
* The service name is exported as <env>-thes-sbs-ecs-batch-service-name
