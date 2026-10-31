"""Strict, browser-originated control messages for the local Phase II WebSocket.

The browser is a UI controller, never a trusted camera/BLE sensor. Only a
small allow-list of UI commands can be translated to engine events.
"""


class InvalidUICommand(ValueError):
    """A browser command doesn't match the supported local protocol."""


def to_engine_event(message):
    """Translate a validated browser command into a server-attributed event.

    Wire format:
      {"type":"command","action":"mode.selected","payload":{"mode":"gesture"}}
      {"type":"command","action":"game.restart","payload":{}}
    """
    if not isinstance(message, dict) or set(message) != {"type", "action", "payload"}:
        raise InvalidUICommand("Expected type, action and payload fields")
    if message["type"] != "command":
        raise InvalidUICommand("Expected a browser command")
    action = message["action"]
    payload = message["payload"]
    if not isinstance(action, str) or not isinstance(payload, dict):
        raise InvalidUICommand("Invalid command action or payload")

    if action == "mode.selected":
        if set(payload) != {"mode"} or payload["mode"] not in ("gesture", "gaze"):
            raise InvalidUICommand("mode.selected requires gesture or gaze")
        return {"type": "mode.selected", "mode": payload["mode"], "source": "ui_bridge"}

    if action == "game.restart":
        if payload:
            raise InvalidUICommand("game.restart requires an empty payload")
        return {"type": "game.restart", "source": "ui_bridge"}

    # Do not allow browser-generated game.select/camera/BLE/sensor events.
    # game.next will be added when Mohamed's correct-answer state is defined.
    raise InvalidUICommand("Unsupported browser command")
