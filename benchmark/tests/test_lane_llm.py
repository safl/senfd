# SPDX-FileCopyrightText: Simon A. F. Lund <os@safl.dk>
#
# SPDX-License-Identifier: LGPL-2.1-only

import os
import signal
import subprocess
import sys
import time
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
