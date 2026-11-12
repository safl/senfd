#!/usr/bin/env python3

# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

"""
sate, with a local language model choosing the lookups
===========================================================

For each of 'llm.models', on the target: checks the language model's file by its
SHA-256, starts llama.cpp's llama-server on it, on the CPU alone with
'llm.threads' threads, offloading nothing to a GPU, and has sate, run here, answer every question with the language
model choosing the lookups. The target is this machine, unless the config
names another by ssh, in which case sate reaches the server through an ssh
tunnel. Writes '<output>/bench/lanes/llm-<name>.json', and beside it the
server's log and what it ran on. The server is stopped, and the tunnel
closed, whatever happens.

Claim a shared target before running this; the step does not.

Config Arguments
----------------

llm.server: the llama-server binary on the target, or its name on PATH
llm.threads, llm.context, llm.port
llm.models: a list of {name, path, sha256}, on the target

A path may start with '~/', for the home directory on the target.

Retargetable: True
------------------
"""

import logging as log
import shlex
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402

PIDFILE = "/tmp/senfd-bench-llm.pid"


def target_ssh(cijoe) -> Optional[str]:
    """user@host of the target, or None where the target is this machine"""

    name = cijoe.getconf("cijoe.default_target", None)
    ssh = cijoe.getconf(f"cijoe.targets.{name}.ssh", None) if name else None
    return f"{ssh['username']}@{ssh['hostname']}" if ssh else None


def quoted(path: str) -> str:
    """'path' quoted for the shell, a leading '~/' left for it to expand"""

    if path.startswith("~/"):
        return '"$HOME"/' + shlex.quote(path[2:])
    return shlex.quote(path)


def start_command(server, model_path, port, threads, context, log_path):
    """
    The shell command that starts llama-server detached and writes its PID

    The redirections are on the group, not the server alone: a backgrounded
    'cd && server' list is a subshell, and one holding the ssh channel's
    output keeps the command from ever returning. 'exec' makes the PID written
    the server's own, so that stopping it stops the server. A server given
    by its name alone is the one on PATH.

    The server runs on the CPU alone. A llama.cpp built with CUDA offloads to
    a GPU it finds unless told otherwise: '--device none' stops the
    offload, and the empty CUDA_VISIBLE_DEVICES hides the GPU, so that the
    server holds no context on it either.
    """

    hide = "export CUDA_VISIBLE_DEVICES=; "
    if "/" in server:
        run = (
            f"cd {quoted(str(Path(server).parent))} && {hide}"
            f"exec nohup ./{Path(server).name}"
        )
    else:
        run = f"{hide}exec nohup {shlex.quote(server)}"
    return (
        f"({run} -m {model_path} --host 127.0.0.1 --port {port} "
        f"-t {threads} -c {context} --jinja --device none) "
        f"> {log_path} 2>&1 < /dev/null & "
        f"echo $! > {PIDFILE}"
    )


def run_model(cijoe, model, port, records):
    server = cijoe.getconf("llm.server")
    threads, context = (
        cijoe.getconf("llm.threads", 16),
        cijoe.getconf("llm.context", 8192),
    )
    path = quoted(model["path"])
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
    host = target_ssh(cijoe)
    if host:
        tunnel = (
            f"ssh -f -N -M -S {socket(cijoe)} -o BatchMode=yes "
            f"-o ExitOnForwardFailure=yes -L {port}:127.0.0.1:{port} {host}"
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
    _, version = cijoe.run(f"{quoted(server)} --version 2>&1 | tail -2")
    _, cpu = cijoe.run("lscpu | grep -E 'Model name|^CPU\\(s\\)'")
    bench.save(
        records / "lanes" / f"llm-{model['name']}.host.json",
        {
            "model": model,
            "threads": threads,
            "context": context,
            "server": version.output().strip(),
            "cpu": cpu.output().strip(),
            "gpu": "none; llama-server run with --device none and no GPU visible",
        },
    )
    cijoe.get(log_path, str(records / "lanes" / f"llm-{model['name']}.server.log"))
    return err


def stop(cijoe):
    """Stop the server by the PID it was started as, and close the tunnel by
    its control socket; by a pattern, pkill would match its own shell"""

    cijoe.run(f"test -f {PIDFILE} && kill $(cat {PIDFILE}); rm -f {PIDFILE}; true")
    host = target_ssh(cijoe)
    if host:
        sock = socket(cijoe)
        cijoe.run_local(
            f"test -S {sock} && ssh -S {sock} -O exit {host}; rm -f {sock}; true"
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
