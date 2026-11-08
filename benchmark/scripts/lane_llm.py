#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
sate, with a local language model choosing the lookups
===========================================================

For each of 'llm.models', on the target: checks the language model's file by its
SHA-256, starts llama.cpp's llama-server on it, on the CPU with 'llm.threads'
threads, and has sate, run here through an ssh tunnel to it, answer
every question with the language model choosing the lookups. Writes
'<output>/bench/lanes/llm-<name>.json', and beside it the server's log and
what it ran on. The server is stopped, and the tunnel closed, whatever
happens.

Claim the target with dibs before running this; the step does not.

Config Arguments
----------------

llm.server: the llama-server binary on the target
llm.threads, llm.context, llm.port
llm.models: a list of {name, path, sha256}, on the target

Retargetable: True
------------------
"""

import logging as log
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402

PIDFILE = "/tmp/senfd-bench-llm.pid"


def target_ssh(cijoe):
    name = cijoe.getconf("cijoe.default_target")
    ssh = cijoe.getconf(f"cijoe.targets.{name}.ssh")
    return f"{ssh['username']}@{ssh['hostname']}"


def start_command(server, model_path, port, threads, context, log_path):
    """
    The shell command that starts llama-server detached and writes its PID

    The redirections are on the group, not the server alone: a backgrounded
    'cd && server' list is a subshell, and one holding the ssh channel's
    output keeps the command from ever returning. 'exec' makes the PID written
    the server's own, so that stopping it stops the server.
    """

    return (
        f"(cd {shlex.quote(str(Path(server).parent))} && exec nohup "
        f"./{Path(server).name} -m {model_path} --host 127.0.0.1 --port {port} "
        f"-t {threads} -c {context} --jinja) > {log_path} 2>&1 < /dev/null & "
        f"echo $! > {PIDFILE}"
    )


def run_model(cijoe, model, port, records):
    server = cijoe.getconf("llm.server")
    threads, context = (
        cijoe.getconf("llm.threads", 16),
        cijoe.getconf("llm.context", 8192),
    )
    path = shlex.quote(model["path"])
    err, state = cijoe.run(f"sha256sum {path}")
    if err or state.output().split()[0] != model["sha256"]:
        log.error(f"{model['path']} is not of SHA-256 {model['sha256']}")
        return 1
    log_path = f"/tmp/senfd-bench-llm-{model['name']}.log"
    err, _ = cijoe.run(start_command(server, path, port, threads, context, log_path))
    if err:
        return err
    err, _ = cijoe.run(
        f"for i in $(seq 1 120); do curl -sf 127.0.0.1:{port}/health && exit 0; "
        "sleep 2; done; exit 1"
    )
    if err:
        log.error("llama-server did not become healthy")
        return err
    tunnel = (
        f"ssh -f -N -M -S {socket(cijoe)} -o BatchMode=yes "
        f"-o ExitOnForwardFailure=yes -L {port}:127.0.0.1:{port} {target_ssh(cijoe)}"
    )
    err, _ = cijoe.run_local(tunnel)
    if err:
        return err
    out = records / "lanes" / f"llm-{model['name']}.json"
    err, _ = cijoe.run_local(
        f"{bench.python(cijoe)} {Path(__file__).parent / 'run_lane.py'} "
        f"--spec {bench.data_model(cijoe)} --out {out} --lane llm-{model['name']} "
        f"--llm http://127.0.0.1:{port}"
    )
    _, version = cijoe.run(f"{shlex.quote(server)} --version 2>&1 | tail -2")
    _, cpu = cijoe.run("lscpu | grep -E 'Model name|^CPU\\(s\\)'")
    bench.save(
        records / "lanes" / f"llm-{model['name']}.host.json",
        {
            "model": model,
            "threads": threads,
            "context": context,
            "server": version.output().strip(),
            "cpu": cpu.output().strip(),
            "gpu": "none; llama-server run with no GPU offload",
        },
    )
    cijoe.get(log_path, str(records / "lanes" / f"llm-{model['name']}.server.log"))
    return err


def stop(cijoe):
    """Stop the server by the PID it was started as, and close the tunnel by
    its control socket; by a pattern, pkill would match its own shell"""

    cijoe.run(f"test -f {PIDFILE} && kill $(cat {PIDFILE}); rm -f {PIDFILE}; true")
    sock = socket(cijoe)
    cijoe.run_local(
        f"test -S {sock} && ssh -S {sock} -O exit {target_ssh(cijoe)}; rm -f {sock}; true"
    )


def socket(cijoe) -> Path:
    return bench.workdir(cijoe) / "tunnel.sock"


def main(args, cijoe):
    port = cijoe.getconf("llm.port", 8088)
    records = bench.records(cijoe)
    for model in cijoe.getconf("llm.models", []) or []:
        try:
            err = run_model(cijoe, model, port, records)
        finally:
            stop(cijoe)
        if err:
            return err
    return 0
