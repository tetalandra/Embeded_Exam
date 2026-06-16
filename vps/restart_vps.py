import paramiko
from pathlib import Path

HOST = "157.173.101.159"
USER = "user268"
PWD = "Q@7Z!RK9"
REMOTE = "/home/user268/exam"
local = Path(__file__).resolve().parent / "exam"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PWD, timeout=20)

sftp = client.open_sftp()
for name in ["start.sh", "app.py", "dashboard.html"]:
    sftp.put(str(local / name), f"{REMOTE}/{name}")
    print("Uploaded", name)
sftp.close()

cmds = [
    "chmod +x /home/user268/exam/start.sh",
    "cd /home/user268/exam && bash start.sh",
    "sleep 3",
    "ss -tlnp | grep 8268",
    "ss -tlnp | grep 9268",
    "curl -s http://127.0.0.1:8268/health",
    "tail -8 /home/user268/exam/app.log",
]

for cmd in cmds:
    print(">>>", cmd)
    _, stdout, stderr = client.exec_command(cmd)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err:
        print("ERR:", err)

client.close()
