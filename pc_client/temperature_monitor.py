#!/usr/bin/env python3
"""
Embedded Practical Exam - Part 2
Read temperature from Arduino serial port, display in real time,
publish to MQTT broker, and serve a local web dashboard.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import paho.mqtt.client as mqtt
import serial
from dotenv import load_dotenv

TEMP_PATTERN = re.compile(r"^TEMP:(?P<value>-?\d+(?:\.\d+)?)\s*$")

DEFAULT_SERIAL_PORT = "COM3"
DEFAULT_BAUD_RATE = 9600
DEFAULT_MQTT_TOPIC = "embedded/exam/temperature"
DEFAULT_DASHBOARD_PORT = 8080

latest_state = {
    "candidate": "",
    "temperature": None,
    "unit": "C",
    "updated_at": None,
    "mqtt_topic": DEFAULT_MQTT_TOPIC,
    "mqtt_connected": False,
}
state_lock = threading.Lock()


def load_config() -> dict:
    load_dotenv("config.env")

    return {
        "serial_port": os.getenv("SERIAL_PORT", DEFAULT_SERIAL_PORT),
        "baud_rate": int(os.getenv("BAUD_RATE", str(DEFAULT_BAUD_RATE))),
        "mqtt_broker": os.getenv("MQTT_BROKER", "").strip(),
        "mqtt_port": int(os.getenv("MQTT_PORT", "1883")),
        "mqtt_topic": os.getenv("MQTT_TOPIC", DEFAULT_MQTT_TOPIC),
        "mqtt_username": os.getenv("MQTT_USERNAME", "").strip(),
        "mqtt_password": os.getenv("MQTT_PASSWORD", "").strip(),
        "candidate_name": os.getenv("CANDIDATE_NAME", "Unknown Candidate"),
        "dashboard_port": int(os.getenv("DASHBOARD_PORT", str(DEFAULT_DASHBOARD_PORT))),
        "enable_dashboard": os.getenv("ENABLE_DASHBOARD", "true").lower() in {
            "1",
            "true",
            "yes",
        },
    }


def parse_temperature_line(line: str) -> float | None:
    match = TEMP_PATTERN.match(line.strip())
    if not match:
        return None
    return float(match.group("value"))


def update_state(
    candidate: str,
    temperature: float,
    mqtt_topic: str,
    mqtt_connected: bool,
) -> None:
    with state_lock:
        latest_state["candidate"] = candidate
        latest_state["temperature"] = round(temperature, 2)
        latest_state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        latest_state["mqtt_topic"] = mqtt_topic
        latest_state["mqtt_connected"] = mqtt_connected


class DashboardHandler(BaseHTTPRequestHandler):
    dashboard_html = ""

    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.dashboard_html.encode("utf-8"))
            return

        if self.path == "/api/latest":
            with state_lock:
                payload = dict(latest_state)
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


def start_dashboard_server(port: int) -> ThreadingHTTPServer:
    html_path = Path(__file__).with_name("dashboard.html")
    DashboardHandler.dashboard_html = html_path.read_text(encoding="utf-8")
    server = ThreadingHTTPServer(("127.0.0.1", port), DashboardHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def build_mqtt_client(cfg: dict) -> tuple[mqtt.Client | None, bool]:
    broker = cfg["mqtt_broker"]
    if not broker or broker in {"your.vps.hostname.or.ip", "your-vps-ip-or-hostname"}:
        print("MQTT broker not configured in config.env — running in serial-only mode.")
        print("Set MQTT_BROKER to your VPS address to publish to the exam dashboard.\n")
        return None, False

    connected = threading.Event()

    def on_connect(client, userdata, flags, reason_code, properties) -> None:
        if reason_code == 0:
            connected.set()
            with state_lock:
                latest_state["mqtt_connected"] = True
            print(f"MQTT connected to {broker}:{cfg['mqtt_port']}")
        else:
            print(f"MQTT connection failed: {reason_code}")

    def on_disconnect(client, userdata, disconnect_flags, reason_code, properties) -> None:
        with state_lock:
            latest_state["mqtt_connected"] = False
        if reason_code != 0:
            print(f"MQTT disconnected (reason: {reason_code})")

    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect

    if cfg["mqtt_username"]:
        client.username_pw_set(cfg["mqtt_username"], cfg["mqtt_password"] or None)

    try:
        client.connect(broker, cfg["mqtt_port"], keepalive=60)
        client.loop_start()
        if not connected.wait(timeout=8):
            print("MQTT broker unreachable — continuing with serial + local dashboard only.\n")
            client.loop_stop()
            client.disconnect()
            return None, False
        return client, True
    except Exception as exc:
        print(f"MQTT error: {exc}")
        print("Continuing with serial + local dashboard only.\n")
        return None, False


def publish_temperature(
    client: mqtt.Client | None,
    topic: str,
    candidate: str,
    temperature: float,
) -> None:
    if client is None:
        return

    payload = {
        "candidate": candidate,
        "temperature": round(temperature, 2),
        "unit": "C",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }
    client.publish(topic, json.dumps(payload), qos=0, retain=False)


def display_temperature(candidate: str, temperature: float) -> None:
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {candidate} | Temperature: {temperature:.2f} C", flush=True)


def run_monitor(cfg: dict) -> None:
    print("Embedded Temperature Monitor")
    print("-" * 40)
    print(f"Serial port : {cfg['serial_port']} @ {cfg['baud_rate']} baud")
    print(f"MQTT broker : {cfg['mqtt_broker'] or '(not set)'}:{cfg['mqtt_port']}")
    print(f"MQTT topic  : {cfg['mqtt_topic']}")
    if cfg["enable_dashboard"]:
        print(f"Dashboard   : http://localhost:{cfg['dashboard_port']}")
    print("-" * 40)
    print("Waiting for Arduino data... (Ctrl+C to stop)\n")

    dashboard_server = None
    if cfg["enable_dashboard"]:
        dashboard_server = start_dashboard_server(cfg["dashboard_port"])

    with state_lock:
        latest_state["candidate"] = cfg["candidate_name"]
        latest_state["mqtt_topic"] = cfg["mqtt_topic"]

    mqtt_client, mqtt_connected = build_mqtt_client(cfg)

    try:
        with serial.Serial(
            port=cfg["serial_port"],
            baudrate=cfg["baud_rate"],
            timeout=1,
        ) as ser:
            time.sleep(2)

            while True:
                raw = ser.readline()
                if not raw:
                    continue

                line = raw.decode("utf-8", errors="ignore").strip()
                if not line:
                    continue

                temperature = parse_temperature_line(line)
                if temperature is None:
                    continue

                display_temperature(cfg["candidate_name"], temperature)
                update_state(
                    cfg["candidate_name"],
                    temperature,
                    cfg["mqtt_topic"],
                    mqtt_connected,
                )
                publish_temperature(
                    mqtt_client,
                    cfg["mqtt_topic"],
                    cfg["candidate_name"],
                    temperature,
                )

    except serial.SerialException as exc:
        print(f"Serial error: {exc}", file=sys.stderr)
        print("Check SERIAL_PORT in config.env and close Arduino Serial Monitor.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        if mqtt_client is not None:
            mqtt_client.loop_stop()
            mqtt_client.disconnect()
        if dashboard_server is not None:
            dashboard_server.shutdown()


def main() -> None:
    parser = argparse.ArgumentParser(description="Arduino temperature MQTT monitor")
    parser.add_argument(
        "--config",
        default="config.env",
        help="Path to config.env file (default: config.env)",
    )
    args = parser.parse_args()

    if args.config != "config.env":
        load_dotenv(args.config)

    cfg = load_config()
    run_monitor(cfg)


if __name__ == "__main__":
    main()
