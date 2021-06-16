import os
import json
import time

import requests
from functools import wraps

from celery import Celery
from celery.utils.log import get_task_logger

from .celery_tasks import http as http_task
from .celery_tasks import socket_ping as socket_ping_task

from dotenv import dotenv_values
from .secrets import decrypt

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "celery_admin.settings")

logger = get_task_logger(__name__)

app = Celery("celery_admin")

app.config_from_object("django.conf:settings", namespace="CELERY")


app.autodiscover_tasks()

STATUS_SUCCESS_LABEL = "success"
STATUS_ERROR_LABEL = "error"

LOG_LEVEL_ERROR = "error"
LOG_LEVEL_INFO = "info"
LOG_LEVEL_DEBUG = "debug"

RECORD_TASK_RESULTS_PATH = dotenv_values(os.environ["DOTENV_PATH"])["TASK_RESULTS_PATH"]

logger.info(f"Record task results path: {RECORD_TASK_RESULTS_PATH}")


### Global


def handle_task(func):
    @wraps(func)
    def inner(*args, **kwargs):
        body = kwargs.get("body")
        t_begin = time.time()

        try:
            if not body:
                raise Exception("No body in the task definition")

            params = body.get("params")

            if not params:
                raise Exception("No params in the task definition")

            result = func(*args, **kwargs)
            result["status"] = STATUS_SUCCESS_LABEL

            return record_task_result(LOG_LEVEL_INFO, body, result, t_begin=t_begin)

        except Exception as e:
            return record_task_result(
                LOG_LEVEL_ERROR,
                body,
                {"error": f"{e}", "status": STATUS_ERROR_LABEL},
                t_begin=t_begin,
            )

    return inner


def write_task_result_file(msg):
    logger.info(f"writing... {RECORD_TASK_RESULTS_PATH}")
    log_file = open(RECORD_TASK_RESULTS_PATH, "a")
    log_file.write(f"{json.dumps(msg)}\n")
    log_file.close()


def record_task_result(level, request_body, result, t_begin=None):
    result = result or {}

    if t_begin:
        result["duration"] = time.time() - t_begin

    logger.debug(f"record result - request body: {request_body}, result: {result}")

    msg = {
        "level": level,
        "status": result["status"],
        "body": request_body,
        "result": result,
    }

    write_task_result_file(msg)

    return msg


### Main tasks


@app.task(bind=True)
@handle_task
def http(self, **kwargs):
    return http_task.task(**kwargs)


@app.task(bind=True)
@handle_task
def socket_ping(self, **kwargs):
    return socket_ping_task.task(**kwargs)


@app.task(bind=True)
def ssh(self, **kwargs):
    # TODO: pass resource id

    params = json.loads(decrypt(kwargs.get("encrypted_params")))


@app.task(bind=True)
def debug_task(self):
    # encrypted_resource = {
    #
    # }
    dec = decrypt(
        "gAAAAABgruSZwSlU_kge70MFTP474_riUujZYwWNi7Xcm-IFHcganatg7TxQ8b_WiRbQqp0XFeR0XreNjKLNQksqRGSoyWY50A=="
    )
    print(f"decrypted -> {dec}")
    print(f"Request: {self.request!r}")


@app.task(bind=True)
def hello_world(self):
    print("Hello world ;)!")
