"""Deploy exam dashboard to VPS and start services."""
from __future__ import annotations

import os
from pathlib import Path

import paramiko

HOST = "157.173.101.159"
USER = "user268"
PASSWORD = "Q@7Z!RK9"
REMOTE_DIR = "/home/user268/exam"
LOCAL_DIR = Path(__file__).resolve().parent / "exam"


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASSWORD, timeout=20)

    client.exec_command(f"mkdir -p {REMOTE_DIR}")
    sftp = client.open_sftp()

    for name in ["app.py", "dashboard.html", "start.sh"]:
        local = LOCAL_DIR / name
        remote = f"{REMOTE_DIR}/{name}"
        sftp.put(str(local), remote)
        print(f"Uploaded {name}")

    sftp.close()

    commands = [
        f"chmod +x {REMOTE_DIR}/start.sh",
        f"pkill -f '{REMOTE_DIR}/app.py' || true",
        "sleep 1",
        f"cd {REMOTE_DIR} && ./start.sh",
        "sleep 2",
        "(crontab -l 2>/dev/null | grep -v 'exam/start.sh'; echo '@reboot /home/user268/exam/start.sh') | crontab -",
        "crontab -l",
        "ss -tlnp | grep -E '8268|9268' || true",
        "curl -s http://127.0.0.1:8268/health || true",
    ]

    for cmd in commands:
        print(">>>", cmd)
        _, stdout, stderr = client.exec_command(cmd)
        out = stdout.read().decode()
        err = stderr.read().decode()
        if out:
            print(out)
        if err:
            print(err)

    client.close()
    print("\nDeploy complete.")
    print("VPS Dashboard: http://157.173.101.159:9268")
    print("VPS API:       http://157.173.101.159:8268/api/latest")


if __name__ == "__main__":
    main()
