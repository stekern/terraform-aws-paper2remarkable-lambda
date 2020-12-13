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
import sys
import logging
import subprocess

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def lambda_handler(event, context):
    logger.debug("Lambda triggered with event '%s'", event)

    ssm_parameter_name = os.environ["SSM_PARAMETER_NAME"]

    # Check if the invocation comes from API Gateway or not
    payload = json.loads(event["body"]) if "body" in event else event
    ssm = boto3.client("ssm")
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
        out = subprocess.run(["p2r"] + args + [file], capture_output=True)
        logger.debug("paper2remarkable output %s", out)
        if out.returncode == 0:
            successes[file] = out
        else:
            failures[file] = out
            logger.warn("paper2remarkable command had non-zero exit")
    status_code = 200 if len(successes) == len(payload["inputs"]) else 500

    # Publish message to SNS on failures
    if len(failures) and os.environ.get("SNS_TOPIC_ARN", None):
        sns = boto3.resource("sns")
        sns_topic = sns.Topic(os.environ["SNS_TOPIC_ARN"])
        messages = [
            "\n".join(
                [
                    f"Input: {file}",
                    "--- STDOUT ---",
                    output.stdout.decode(),
                    "",
                    "--- STDERR ---",
                    output.stderr.decode(),
                    "",
                ]
            )
            for file, output in failures.items()
        ]
        sns_topic.publish(
            Subject=f"{os.environ.get('AWS_LAMBDA_FUNCTION_NAME', 'paper2remarkable-lambda')} failed 😥",
            Message="\n\n".join(messages),
        )

    response = {"statusCode": status_code}
    return response
