import datetime
import shlex
import subprocess
import time
from typing import List

from behave import given, then, when
from behave.runner import Context
from hamcrest import assert_that, equal_to

from features.util import lxc_exec


PPA_URL = "http://ppa.launchpad.net/canonical-server/ua-client-daily/ubuntu/"

@given("ubuntu-advantage-tools is installed")
def given_uat_is_installed(context):
    process = lxc_exec(context, ["apt-cache", "policy"], capture_output=True, text=True)
    if PPA_URL in process.stdout:
        return
    lxc_exec(context, ["add-apt-repository", "ppa:canonical-server/ua-client-daily", "--yes"])
    lxc_exec(context, ["apt-get", "update", "-qq"])
    lxc_exec(
        context, ["apt-get", "install", "-qq", "-y", "ubuntu-advantage-tools"]
    )


@when("I run `{command}` as non-root")
def when_i_run_command(context, command):
    process = lxc_exec(
        context, shlex.split(command), capture_output=True, text=True
    )
    context.process = process


@then("I will see the following on stdout")
def then_i_will_see_on_stdout(context):
    assert_that(context.process.stdout.strip(), equal_to(context.text))


@then("I will see the following on stderr")
def then_i_will_see_on_stderr(context):
    assert_that(context.process.stderr.strip(), equal_to(context.text))
