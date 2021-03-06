#!/usr/bin/env python
#
# Copyright (C) 2020 Erlend Ekern <dev@ekern.me>
#
# Distributed under terms of the MIT license.

"""
A Lambda wrapper for paper2remarkable.
"""

import boto3
import json
import os
import logging
import selectors
import signal
import subprocess

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# Avoid re-initializing clients and resources across executions
ssm = boto3.client("ssm")
if os.environ.get("SNS_TOPIC_ARN", None):
    sns = boto3.resource("sns")
    sns_topic = sns.Topic(os.environ["SNS_TOPIC_ARN"])
else:
    sns_topic = None


def timeout_handler(signal_number, stack_frame):
    """Raise exception if we are close to Lambda timeout limit"""
    logger.warn("Lambda is about to time out")
    if sns_topic:
        sns_topic.publish(
            Subject=f"{os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'paper2remarkable-lambda')} timed out ⏰",
            Message="The Lambda function timed out",
        )
    raise Exception("Time exceeded")


signal.signal(signal.SIGALRM, timeout_handler)


def lambda_handler(event, context):
    signal.alarm((context.get_remaining_time_in_millis() // 1000) - 2)
    logger.debug("Lambda triggered with event '%s'", event)

    ssm_parameter_name = os.environ["SSM_PARAMETER_NAME"]

    # Check if the invocation comes from API Gateway or not
    payload = json.loads(event["body"]) if "body" in event else event
    decrypted = ssm.get_parameter(Name=ssm_parameter_name, WithDecryption=True)
    rmapi_config = json.loads(decrypted["Parameter"]["Value"])
    if not all(
        key in rmapi_config for key in ["rmapi_user_token", "rmapi_device_token"]
    ):
        raise ValueError("SSM parameter is missing required keys")

    # Does not seem like paper2remarkable is set up as a Python library, so we pass in
    # parameters by simulating that we're calling it from the command-line
    args = [
        *(["--verbose"] if payload.get("verbose", True) else []),
        *(["--blank"] if payload.get("blank", False) else []),
        *(["--center"] if payload.get("center", False) else []),
        *(["--right"] if payload.get("right", False) else []),
        *(["--no-crop"] if payload.get("disable_cropping", False) else []),
        *(
            ["--remarkable-path", payload["remarkable_path"]]
            if payload.get("remarkable_path", None)
            else []
        ),
    ]

    credentials_file = "/tmp/rmapi.conf"
    with open(credentials_file, "w") as f:
        f.write(
            f"""
usertoken: {rmapi_config['rmapi_user_token']}
devicetoken: {rmapi_config['rmapi_device_token']}
"""
        )
    logger.debug("Stored rmapi credentials in '%s'", credentials_file)
    os.environ["RMAPI_CONFIG"] = credentials_file

    successes = {}
    failures = {}
    for file in payload["inputs"]:
        # We get some weird errors at times:
        # `[Errno 2] No such file or directory`
        # that seem to stem from inability to start a shell:
        # `shell-init: error retrieving current directory: getcwd: cannot access parent directories: No such file or directory`
        # This is most likely due to reuse of Lambda execution contexts,
        # as the error does not seem to occur on clean executions.
        # Only processing a single input at a time and changing the
        # directory to a known directory seems to fix it.
        logger.debug("Running paper2remarkable for file '%s'", file)
        os.chdir("/tmp")
        proc = subprocess.Popen(
            ["p2r"] + args + [file], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        sel = selectors.DefaultSelector()
        sel.register(proc.stdout, selectors.EVENT_READ)
        sel.register(proc.stderr, selectors.EVENT_READ)
        output = {"stdout": "", "stderr": ""}
        # Continuously log stdout and stderr while
        # process is running
        while proc.poll() is None:
            for key, _ in sel.select():
                data = key.fileobj.read1().decode()
                if not data:
                    continue
                if key.fileobj is proc.stdout:
                    output["stdout"] += data
                    logger.debug(data)
                else:
                    output["stderr"] += data
                    logger.error(data)
        return_code = proc.returncode
        if return_code == 0:
            successes[file] = output
        else:
            failures[file] = output
            logger.warn("paper2remarkable command had non-zero exit")

    # Publish message to SNS on failures
    if len(failures) and sns_topic:
        messages = [
            "\n".join(
                [
                    f"Input: {file}",
                    "--- STDOUT ---",
                    output["stdout"],
                    "",
                    "--- STDERR ---",
                    output["stderr"],
                    "",
                ]
            )
            for file, output in failures.items()
        ]
        sns_topic.publish(
            Subject=f"{os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'paper2remarkable-lambda')} failed 😥",
            Message="\n\n".join(messages),
        )

    status_code = 200 if len(failures) == 0 else 500
    response = {"statusCode": status_code}
    return response
