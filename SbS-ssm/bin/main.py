#!/usr/bin/env python

import boto3
import logging
import sys
import os
import json

import calculated_parameters

logging.basicConfig(
    level=logging.WARN,
    handlers=[logging.StreamHandler(sys.stdout)])
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

def get_config():
    config_file = os.path.join(get_parent_folder_path(), "config", "env.json")
    with open(config_file) as cf:
        config = json.load(cf)
        return config

def get_parent_folder_path():
    parent_folder = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    return parent_folder

def main():
    config = get_config()

    boto3.setup_default_session(region_name=config['region'])
    ssm_client = boto3.client('ssm')

    for parameter in config['parameters']:
        parameter_type = parameter['Type']
        parameter_value = parameter['Value']
        parameter_path = parameter['Path']

        if parameter_value.endswith("()"):
            method_name = parameter_value[:-2]
            if method_name in dir(calculated_parameters):
                parameter_value = getattr(calculated_parameters, method_name)()

        response = ssm_client.put_parameter(Name=parameter_path, Value=parameter_value, Type=parameter_type, Overwrite=True)
        logger.debug("Put '%s' to ssm response: %s", parameter_path, response)
        logger.info("'%s' saved to ssm.", parameter_path)


if __name__ == "__main__":
    main()
