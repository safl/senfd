# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import os
import signal
import subprocess
import sys
import time
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))
import lane_llm  # noqa: E402


def test_the_server_is_started_detached_and_its_own_pid_is_written(
    tmp_path, monkeypatch
):
    server = tmp_path / "bin" / "llama-server"
    server.parent.mkdir()
    server.write_text("#!/bin/sh\nexec sleep 30\n")
    server.chmod(0o755)
    pidfile = tmp_path / "server.pid"
    monkeypatch.setattr(lane_llm, "PIDFILE", str(pidfile))

    command = lane_llm.start_command(
        str(server), "model.gguf", 8088, 16, 8192, str(tmp_path / "server.log")
    )
    # As over ssh, by bash: the command must return, its output at EOF, while the
    # server keeps running.
    done = subprocess.run(
        ["bash", "-c", command],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=5,
    )
    assert done.returncode == 0
    pid = int(pidfile.read_text())
    try:
        for _ in range(40):  # The exec may not have happened yet
            command_line = subprocess.run(
                ["ps", "-p", str(pid), "-o", "command="], capture_output=True, text=True
            ).stdout
            if "sleep" in command_line:
                break
            time.sleep(0.05)
        assert "sleep" in command_line
    finally:
        os.kill(pid, signal.SIGTERM)


class Config:
    """A cijoe of a config's options alone, for the steps reading them"""

    def __init__(self, options):
        self.options = options

    def getconf(self, key, default=None):
        value = self.options
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return default
            value = value[part]
        return value


def test_the_default_config_runs_the_server_here_and_finds_it_and_its_models():
    """With no target named, llama-server runs on this machine, by its name
    on PATH, with no tunnel; the language models are in the home directory"""

    options = tomllib.loads(
        (Path(__file__).parents[1] / "configs" / "default.toml").read_text()
    )
    cijoe = Config(options)
    assert lane_llm.target_ssh(cijoe) is None
    assert "cd " not in lane_llm.start_command(
        cijoe.getconf("llm.server"), "m.gguf", 8088, 8, 8192, "log"
    )
    for model in cijoe.getconf("llm.models"):
        assert lane_llm.quoted(model["path"]).startswith('"$HOME"/')


def test_a_target_named_by_ssh_is_reached_through_a_tunnel():
    cijoe = Config(
        {
            "cijoe": {
                "default_target": "far",
                "targets": {"far": {"ssh": {"username": "u", "hostname": "h"}}},
            }
        }
    )
    assert lane_llm.target_ssh(cijoe) == "u@h"


def test_a_path_in_the_home_directory_is_expanded_by_the_shell_and_quoted():
    path = "~/my models/a.gguf"
    expanded = subprocess.run(
        ["bash", "-c", f"printf %s {lane_llm.quoted(path)}"],
        capture_output=True,
        text=True,
        env={"HOME": "/home/x"},
    ).stdout
    assert expanded == "/home/x/my models/a.gguf"


def test_a_server_by_its_name_alone_is_run_from_path(tmp_path, monkeypatch):
    bin = tmp_path / "bin"
    bin.mkdir()
    (bin / "llama-server").write_text('#!/bin/sh\necho "$@"\n')
    (bin / "llama-server").chmod(0o755)
    monkeypatch.setattr(lane_llm, "PIDFILE", str(tmp_path / "server.pid"))
    log_path = tmp_path / "server.log"

    command = lane_llm.start_command(
        "llama-server", "m.gguf", 8088, 8, 8192, str(log_path)
    )
    env = {**os.environ, "PATH": f"{bin}:{os.environ['PATH']}"}
    subprocess.run(["bash", "-c", command + "; wait"], env=env, check=True, timeout=5)
    assert log_path.read_text().startswith("-m m.gguf")
