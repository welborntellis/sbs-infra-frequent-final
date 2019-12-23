import json
import os


class Config:
    def get_config(self, cfg_file_path):
        env_json = ''
        # json file to refer key value pair to create stack.
        try:
            env_json = os.path.join(cfg_file_path)
            print('Reading config from {}'.format(env_json))
            # Read json file and take value from it.
            return json.load(open(env_json))
        except Exception as e:
            print('Exception occurred while reading config from {} : {}'.format(
                env_json, e))
