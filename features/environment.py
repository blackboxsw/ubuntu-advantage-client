from behave import fixture
from behave import use_fixture
from behave.runner import Context

import time
from util import lxc_exec

import subprocess

CONTAINER_PREFIX = "behave-test-"
DEFAULT_SERIES = "trusty"

def _wait_for_boot(context: Context) -> None:
    retries = [2] * 5
    for sleep_time in retries:
        process = lxc_exec(
            context, ["runlevel"], capture_output=True, text=True
        )
        try:
            _, runlevel = process.stdout.strip().split(" ", 2)
        except ValueError:
            print("Unexpected runlevel output: ", process.stdout.strip())
            runlevel = None
        if runlevel == "2":
            break
        time.sleep(sleep_time)
    else:
        raise Exception("System did not boot in {}s".format(sum(retries)))


@fixture
def lxc_container(context: Context,  **kwargs):
    series = kwargs.get('series', DEFAULT_SERIES)
    context.container_name = CONTAINER_PREFIX + series + "-shared"
    process = subprocess.run(["lxc", "list"], capture_output=True, text=True)
    if context.container_name in process.stdout:
        context.container_launched = False
    else:
        context.container_launched = True
        subprocess.run(
            ["lxc", "launch", "ubuntu-daily:trusty", context.container_name])

    def cleanup_container():
        if context.container_launched:
            subprocess.run(["lxc", "stop", context.container_name])
            subprocess.run(["lxc", "delete", context.container_name])

    context.add_cleanup(cleanup_container)

    _wait_for_boot(context)


def before_tag(context, tag):
    if tag.startswith("fixture.lxc_container"):
        return use_fixture(lxc_container, context)
