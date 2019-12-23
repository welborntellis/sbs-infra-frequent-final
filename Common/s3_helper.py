import os
import sys
import time

import boto3

from Common.Config import Config

env = str(sys.argv[1])
dir_name = str(sys.argv[2])

dir_path = os.path.dirname(os.path.realpath(__file__))
base_dir = os.path.split(dir_path)[0]

cfg_file_path = os.path.join(base_dir, dir_name, 'config',
                             'sbs_config.{}.json'.format(env))


def upload_files_to_s3():
    config = Config().get_config(cfg_file_path)
    reqfiles = []
    search_path = os.path.join(base_dir, dir_name)
    try:
        s3_bucket_name = config['sbs_s3_bucket']
        for root, dirs, files in os.walk(search_path, topdown=False):
            if os.path.basename(root) not in ['bin', 'config']:
                for name in files:
                    reqfiles.append(os.path.join(root, name))

        __upload_files(reqfiles, s3_bucket_name, dir_name)
    except Exception as e:
        print('Failed to upload files with error {}'.format(str(e)))
        sys.exit(e)

    time.sleep(5)
    print("Successfully Uploaded New code to s3 bucket")


def __upload_files(reqfiles, s3_bucket_name, s3_folder):
    print("Uploading New code to the s3 bucket: {}".format(s3_bucket_name))
    if reqfiles:
        print('Uploading {} files to S3 location {}'
              .format(len(reqfiles),
                      s3_bucket_name + '/Scripts/devops/' + s3_folder))
        for sbs_file in reqfiles:
            file_path = sbs_file.split(s3_folder)[1]
            s3_path = 'Scripts/devops/' + s3_folder + file_path
            s3_resouce = boto3.resource('s3')
            s3_resouce.meta.client.upload_file(sbs_file, s3_bucket_name,
                                               s3_path)

    else:
        print('No files found to be uploaded on S3'.format(len(reqfiles)))
        print('Reqfiles is {}'.format(reqfiles))
        sys.exit(1)


def main():
    upload_files_to_s3()


if __name__ == '__main__':
    main()
