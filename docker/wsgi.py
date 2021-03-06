# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
# A copy of the License is located at
#     http://www.apache.org/licenses/LICENSE-2.0
# or in the "license" file accompanying this file. This file is distributed
# on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either
# express or implied. See the License for the specific language governing
# permissions and limitations under the License.

from mms import mxnet_model_server
import sys
import json
import os
from mms.arg_parser import ArgParser
import fasteners
import subprocess
mms_arg_header = 'MMS Argument'
args = []
found_mms_args = 0

mms_config_path = os.environ['MXNET_MODEL_SERVER_CONFIG']
is_gpu_image = os.environ['MXNET_MODEL_SERVER_GPU_IMAGE']
num_gpu = 1
gpu_parameter = False
LOCK_FILE = '/tmp/tmp_lock_file'
@fasteners.interprocess_locked(LOCK_FILE)
def get_gpu_ids(args, n_gpu):
    args.append('--gpu')
    gpu_id=0
    try:
        with open('/mxnet_model_server/.gpu_id', 'r') as file:
            gpu_id = file.read()
            args.append(str(int(gpu_id )% n_gpu))
        with open('/mxnet_model_server/.gpu_id', 'w') as file:
            file.write(str(int(gpu_id) + 1))
            file.truncate()
    except IOError as e:
        sys.exit("ERROR: failed to setup GPU context")

def read_models_from_file():
    """
    This method reads the models meta-data from a local file. This is used for MMS in
    :return: models meta-data
    """
    mxnet_model_metadata_file = "/mxnet_model_server/.models"
    models = json.load(open(mxnet_model_metadata_file))
    return models


try:
    mms_config_file = open(mms_config_path)
except IOError as e:
    sys.exit("ERROR: File %s could not be located" % mms_config_path)
else:
    print("INFO: Successfully read config file %s.." % mms_config_path)
    with mms_config_file:
        try:
            content = mms_config_file.readlines()
            content = [line.rstrip() for line in content]

            for i, line in enumerate(content):
                line = line.lstrip()
                if line.startswith('#') or line.startswith('$'):
                    continue
                if line.startswith('['):
                    found_mms_args = 1 if mms_arg_header.lower() in line.lower() else 0
                if found_mms_args is 1:
                    if line.startswith('--num-gpu') and content[i+1] != 'optional':
                        num_gpu = int(content[i+1])
                        gpu_parameter = True
                    else:
                        if line.startswith('--') and content[i+1] != 'optional':
                            args.append(line)
                            if line.startswith('--model'):
                                args += content[i + 1].split(' ')
                            else:
                                args.append(content[i + 1])  
        except Exception as e:
            sys.exit("ERROR: Cannot read the open file.")

if is_gpu_image == '1':
    if gpu_parameter == False:
        num_gpu = len(subprocess.check_output(['nvidia-smi','--query-gpu=index','--format=csv']).split('\n')) - 2
    get_gpu_ids(args, num_gpu)
     
# Extract the model's metadata from the file
models = read_models_from_file()
# Parse the arguments
arguments = ArgParser.extract_args(args)
# Instantiate the MMS object to start the MMS app
server = mxnet_model_server.MMS(args=arguments, models=models)
application = server.create_app()
