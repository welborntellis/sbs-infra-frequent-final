'''
Stack.py

   A file to serve Stack operations like create, delete and exist .

   Created: 17-11-2011
'''

import json
import time

import boto3
import botocore


class Stack(object):
    timeout = 180

    def __init__(self, cft_cft_stack_name, cft_template, cfn_role_arn,
                 stack_parameters, template_url=None, template_body=None,
                 region_name='us-east-1', timeout=timeout):
        self.cft_stack_name = cft_cft_stack_name
        self.cft_template = cft_template
        self.cfn_role_arn = cfn_role_arn
        self.stack_parameters = stack_parameters
        self.template_body = template_body
        self.template_url = template_url
        self.timeout = timeout
        self.cf_client = boto3.client('cloudformation', region_name=region_name)
        self.resource = boto3.resource('cloudformation',
                                       region_name=region_name)
        if not template_body and not template_url:
            raise Exception('template_body or template_url should be present.')

    # Validating cloudformation template which will create SbS notification lambda
    def validate_cf_template(self):
        try:
            with open(self.cft_template, 'r') as f:
                response = self.cf_client.validate_template(
                    TemplateBody=f.read()
                )

            print("Successfully validated Cloudformation template.")
            return response
        except Exception as e:
            print('Failed validating cloudformation template: {}'
                  .format(e))
            raise Exception(e)

    def exist(self):
        try:
            self.cf_client.describe_stacks(StackName=self.cft_stack_name)
            print('Stack {} exist.'.format(self.cft_stack_name))
            return True
        except (botocore.exceptions.ValidationError,
                botocore.exceptions.ClientError) as err:
            error_msg = self.boto_exception(err)
            if 'does not exist' in error_msg:
                print('Stack {} does not exist.'.format(self.cft_stack_name))
                return False
            else:
                print('Failed while describing  stack: {}'
                      .format(err))
                raise Exception(err)

    def boto_exception(self, err):
        '''generic error message handler'''
        if hasattr(err, 'error_message'):
            error = err.error_message
        elif hasattr(err, 'message'):
            error = err.message + ' ' + str(err) + ' - ' + str(type(err))
        else:
            error = '%s: %s' % (Exception, err)

        return error

    def delete(self):
        print('Deleting stack {}'.format(self.cft_stack_name))
        try:
            self.cf_client.delete_stack(
                StackName=self.cft_stack_name,
                RoleARN=self.cfn_role_arn)
        except Exception as e:
            print('Error occurred while deleting stack: {}'.format(e))
            raise Exception(e)

    def wait_till_stack_exists(self):
        self.__wait_till_stack_exists(time.time() + self.timeout)

    def __wait_till_stack_exists(self, timeout):
        if self.exist():
            print("time...............", time.time())
            print("timeout.............", timeout)
            if time.time() > timeout:
                print('Timeout occurred.')
                raise Exception('Timeout occurred.')
            time.sleep(5)
            self.__wait_till_stack_exists(timeout)
        else:
            print('Stack {} does not exist'.format(self.cft_stack_name))

    def create(self):
        try:
            print('Creating Stack {}'.format(self.cft_stack_name))

            if self.template_url:
                self.cf_client.create_stack(
                    StackName=self.cft_stack_name,
                    TemplateURL=self.template_url,
                    Parameters=self.stack_parameters,
                    RoleARN=self.cfn_role_arn
                )
            else:
                self.cf_client.create_stack(
                    StackName=self.cft_stack_name,
                    TemplateBody=self.template_body,
                    Parameters=self.stack_parameters,
                    RoleARN=self.cfn_role_arn
                )
        except Exception as e:
            print('Error occurred while creating stack {}: {}'.format(
                self.cft_stack_name, e))
            raise Exception(e)

    def wait_till_stack_create(self):
        return self.__wait_till_stack_create(time.time() + self.timeout)

    def __wait_till_stack_create(self, timeout):
        if time.time() > timeout:
            print('Timeout occurred.')
            raise Exception('Timeout occurred.')
        else:
            status = self.get_status()
            if status == 'CREATE_COMPLETE':
                print('Stack {} creation complete. Status: {}'.format(
                    self.cft_stack_name, status))
            elif status == 'CREATE_FAILED' or 'ROLLBACK' in status:
                raise Exception('Stack {} creation failed. Status: {}'.format(
                    self.cft_stack_name, status))
            elif status == 'CREATE_IN_PROGRESS':
                print('Stack {} creation in progress. Status: {}'.format(
                    self.cft_stack_name, status))
                time.sleep(5)
                self.__wait_till_stack_create(timeout)

    def wait_till_stack_update(self):
        return self.__wait_till_stack_update(time.time() + self.timeout)

    def __wait_till_stack_update(self, timeout):
        if time.time() > timeout:
            print('Timeout occurred.')
            raise Exception('Timeout occurred.')
        else:
            status = self.get_status()
            if status == 'UPDATE_COMPLETE':
                print('Stack {} update complete. Status: {}'.format(
                    self.cft_stack_name, status))
            elif status == 'UPDATE_FAILED' or 'UPDATE_ROLLBACK_IN_PROGRESS' in status:
                raise Exception('Stack {} update failed. Status: {}'.format(
                    self.cft_stack_name, status))
            elif status == 'UPDATE_IN_PROGRESS':
                print('Stack {} update in progress. Status: {}'.format(
                    self.cft_stack_name, status))
                time.sleep(5)
                self.__wait_till_stack_update(timeout)

    def get_status(self):
        try:
            return self.resource.Stack(self.cft_stack_name).stack_status
        except Exception as e:
            print(
                'Exception occurred while checking stack {} status. Error: {}'
                    .format(self.cft_stack_name, e))
            raise Exception(e)

    def create_change_set(self):
        print('Creating change set for stack {}'
              .format(self.cft_stack_name))
        response = self.cf_client.create_change_set(
            StackName=self.cft_stack_name,
            TemplateURL=self.template_url,
            TemplateBody=self.template_body,
            Parameters=self.stack_parameters,
            RoleARN=self.cfn_role_arn,
            ChangeSetName=self.cft_stack_name + '-change-set',
            ChangeSetType='UPDATE',
            UsePreviousTemplate=True
        )

        return response

    def list_change_set(self):
        response = self.cf_client.list_change_sets(
            StackName=self.cft_stack_name
        )

        return response

    def update_stack(self):
        try:
            print('Updating stack {}'.format(self.cft_stack_name))
            response = self.cf_client.update_stack(
                StackName=self.cft_stack_name,
                TemplateURL=self.template_url,
                Parameters=self.stack_parameters,
                RoleARN=self.cfn_role_arn,
                UsePreviousTemplate=False
            )
        except botocore.exceptions.ClientError as e:
            print("Exception occurred while updating stack: {}".format(e))
            if str(e).__contains__("No updates are to be performed"):
                return "No updates"
            else:
                raise Exception(
                    "Exception occurred while updating stack: {}".format(e))
        except Exception as e:
            raise Exception(
                "Exception occurred while updating stack: {}".format(e))

        return response

    def update_stack_if_updates_exists(self):
        self.create_change_set()
        change_sets = self.list_change_set()
        if change_sets['summaries']:
            print(json.dumps(self.list_change_set(), indent=2))
            self.update_stack()
        else:
            print('Stack updates not found.')
