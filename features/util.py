from behave.runner import Context
from typing import List
import subprocess

def lxc_exec(context: Context, cmd: List[str], *args, **kwargs):
    return subprocess.run(
        ["lxc", "exec", context.container_name, "--"] + cmd, *args, **kwargs
    )

