#!/usr/bin/env python3
"""VPS temperature dashboard — subscribes to MQTT and serves web UI on port 9268."""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import paho.mqtt.client as mqtt

MQTT_BROKER = os.getenv("MQTT_BROKER", "157.173.101.159")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC = os.getenv("MQTT_TOPIC", "embedded/exam/temperature")
MQTT_USERNAME = os.getenv("MQTT_USERNAME", "user268")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD", "")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "9268"))
API_PORT = int(os.getenv("API_PORT", "8268"))
CANDIDATE_NAME = os.getenv("CANDIDATE_NAME", "Landra")

BASE_DIR = Path(__file__).resolve().parent
DASHBOARD_HTML = (BASE_DIR / "dashboard.html").read_text(encoding="utf-8")

state = {
    "candidate": CANDIDATE_NAME,
    "temperature": None,
    "unit": "C",
    "updated_at": None,
    "mqtt_topic": MQTT_TOPIC,
    "mqtt_connected": False,
}
lock = threading.Lock()


def on_connect(client, userdata, flags, reason_code, properties) -> None:
    if reason_code == 0:
        client.subscribe(MQTT_TOPIC)
        with lock:
            state["mqtt_connected"] = True
        print(f"MQTT connected, subscribed to {MQTT_TOPIC}")
    else:
        print(f"MQTT connect failed: {reason_code}")


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties) -> None:
    with lock:
        state["mqtt_connected"] = False


def on_message(client, userdata, msg) -> None:
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        temperature = float(payload.get("temperature"))
        candidate = payload.get("candidate", CANDIDATE_NAME)
    except (json.JSONDecodeError, TypeError, ValueError):
        return

    with lock:
        state["candidate"] = candidate
        state["temperature"] = round(temperature, 2)
        state["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        state["mqtt_connected"] = True

    print(f"MQTT RX: {candidate} {temperature:.2f} C")


def start_mqtt() -> None:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.username_pw_set(MQTT_USERNAME, MQTT_PASSWORD)
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT, keepalive=60)
    client.loop_forever()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path in ("/", "/index.html"):
            body = DASHBOARD_HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/api/latest":
            with lock:
                payload = dict(state)
                payload["source"] = "VPS MQTT subscriber"
            body = json.dumps(payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if self.path == "/health":
            body = b'{"status":"ok"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()


class ApiHandler(Handler):
    """Port 8268 — JSON API only."""


def run_http(port: int, handler: type) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), handler)
    print(f"HTTP listening on 0.0.0.0:{port}")
    server.serve_forever()


def main() -> None:
    threading.Thread(target=start_mqtt, daemon=True).start()
    threading.Thread(target=run_http, args=(API_PORT, ApiHandler), daemon=True).start()
    run_http(DASHBOARD_PORT, Handler)


if __name__ == "__main__":
    main()
