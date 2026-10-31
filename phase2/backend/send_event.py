"""Send real adapter events, or manually test the pipeline."""
import argparse
import json
import socket


def send(event, host="127.0.0.1", port=8765):
    data = (json.dumps(event, separators=(",", ":")) + "\n").encode()
    with socket.create_connection((host, port), timeout=4) as connection:
        connection.sendall(data)
        response = b""
        while not response.endswith(b"\n"):
            chunk = connection.recv(4096)
            if not chunk:
                break
            response += chunk
    return json.loads(response) if response else {"ok": False, "error": "No reply"}

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("json_event", help='Example: {"type":"game.restart","source":"simulator"}')
    args = p.parse_args()
    print(send(json.loads(args.json_event)))
