"""Canal de actualización e instalación NVIDIA para el asistente iniciado por systemd."""

import argparse
import os
import re
import subprocess

HELPER = "/usr/lib/aio-debian-gui/aio-debian-gui-helper"
REQUEST = "##AYUSOS-NVIDIA:"
RESULT = "##AYUSOS-NVIDIA-EXIT:"
SYSTEM_ENV = {"PATH": "/usr/sbin:/usr/bin:/sbin:/bin", "LC_ALL": "C.UTF-8",
              "DEBIAN_FRONTEND": "noninteractive"}


UPDATE_STEPS = ("upgrade", "onboarding-check-upgrade")


def steps_for_driver(repos):
    return ("repos", "nvidia-driver") if repos else ("nvidia-driver",)


def run_session(uid, command):
    """El hijo solo puede solicitar las operaciones previstas por el asistente."""
    if os.geteuid() != 0 or uid <= 0:
        return 2
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, errors="replace",
    ) as wizard:
        channel_open = True
        requested = False

        def forward(line):
            nonlocal channel_open
            if channel_open:
                try:
                    wizard.stdin.write(line)
                    wizard.stdin.flush()
                except BrokenPipeError:
                    channel_open = False

        for line in wizard.stdout:
            request = re.fullmatch(rf"{REQUEST}(update|driver:[01]|reboot)", line.rstrip("\n"))
            if not request:
                print(line, end="", flush=True)
                continue
            operation = request[1]
            if operation.startswith("driver:") and requested:
                forward("[-] Ya se procesó una solicitud NVIDIA en este asistente.\n")
                forward(f"{RESULT}2\n")
                continue
            if operation == "reboot":
                command = ["/usr/bin/systemctl", "--no-block", "reboot"]
            elif operation == "update":
                command = [HELPER, "--lang", "es", *UPDATE_STEPS]
            else:
                requested = True
                command = [HELPER, "--lang", "es", *steps_for_driver(operation.endswith(":1"))]
            try:
                with subprocess.Popen(
                    command,
                    env={**SYSTEM_ENV, "PKEXEC_UID": str(uid)}, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                ) as helper:
                    for progress in helper.stdout:
                        print(progress, end="", flush=True)
                        forward(progress)
                    code = helper.wait()
            except OSError as exc:
                print(str(exc), flush=True)
                forward(f"[-] {exc}\n")
                code = 1
            forward(f"{RESULT}{code}\n")
        return wizard.wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("uid", type=int)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    raise SystemExit(run_session(args.uid, args.command))
