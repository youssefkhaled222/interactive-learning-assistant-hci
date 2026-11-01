"""Phase II local end-to-end integration smoke test (SIMULATED INPUT ONLY).

Run when the backend server is already running:
    python backend/integration_smoke.py

Exercises real TCP JSONL -> Engine -> WebSocket and WebSocket -> Engine paths.
Temporarily changes the server's state and restores guest/gesture at the end.
NEVER present these simulator messages as evidence of actual BLE, pose or gaze.
"""
import argparse
import asyncio
import json
import sys

from websockets.asyncio.client import connect


class ProbeFailure(RuntimeError):
    """A connectivity or state assertion failed."""


async def tcp_event(event, host, port, timeout):
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(host, port), timeout
    )
    try:
        writer.write((json.dumps(event, separators=(",", ":")) + "\n").encode("utf-8"))
        await asyncio.wait_for(writer.drain(), timeout)
        line = await asyncio.wait_for(reader.readline(), timeout)
        if not line:
            raise ProbeFailure("TCP broker closed connection without acknowledging event")
        try:
            return json.loads(line)
        except json.JSONDecodeError as exc:
            raise ProbeFailure("TCP broker sent invalid JSON acknowledgement") from exc
    finally:
        writer.close()
        await writer.wait_closed()


async def ws_message(ws, timeout):
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout)
        return json.loads(raw)
    except asyncio.TimeoutError as exc:
        raise ProbeFailure("Timed out waiting for WebSocket state") from exc
    except json.JSONDecodeError as exc:
        raise ProbeFailure("WebSocket sent invalid JSON") from exc


def assert_state(message, **expected):
    if not isinstance(message, dict) or message.get("type") != "state":
        raise ProbeFailure(f"Expected state message, got {message!r}")
    state = message.get("payload")
    if not isinstance(state, dict):
        raise ProbeFailure("WebSocket state is missing a JSON payload")
    for key, value in expected.items():
        if state.get(key) != value:
            raise ProbeFailure(
                f"Expected {key}={value!r}, got {state.get(key)!r}"
            )
    return state


async def probe(host="127.0.0.1", tcp_port=8765, ws_port=8766,
                timeout=3, print_progress=print):
    """Verify the production socket paths using explicit simulator events.

    Run this only against a DEVELOPMENT server, not a concurrent hardware demo.
    This probe changes the shared learner session and restores guest/gesture.
    """
    url = f"ws://{host}:{ws_port}"
    print_progress("SIMULATED INPUT ONLY — this does not verify real sensor hardware.")
    async with connect(url, open_timeout=timeout) as ws:
        assert_state(await ws_message(ws, timeout))
        print_progress("PASS: Browser receives the initial backend state")

        async def send_and_expect(event, **expected):
            response = await tcp_event(event, host, tcp_port, timeout)
            if response.get("ok") is not True:
                raise ProbeFailure(f"TCP rejected valid event: {response!r}")
            return assert_state(await ws_message(ws, timeout), **expected)

        try:
            state = await send_and_expect({
                "type": "device.discovered",
                "device_id": "demo-device-beginner", "source": "simulator",
            }, level="beginner", user_id="learner_01", event_source="simulator")
            if not state.get("question") or not state["question"].get("prompt"):
                raise ProbeFailure("Beginner profile has no actual question content")
            beginner_prompt = state["question"]["prompt"]
            print_progress(f"PASS: Enrolled demo identity loads beginner content ({beginner_prompt})")

            state = await send_and_expect({
                "type": "device.discovered",
                "device_id": "demo-device-advanced", "source": "simulator",
            }, level="advanced", user_id="learner_02")
            advanced_prompt = (state.get("question") or {}).get("prompt")
            if not advanced_prompt or advanced_prompt == beginner_prompt:
                raise ProbeFailure("Learning content did not change with the profile")
            print_progress(f"PASS: Advanced learner receives different content ({advanced_prompt})")

            await send_and_expect({
                "type": "camera.status", "ready": True, "source": "simulator",
            }, camera_ready=True)
            await send_and_expect({
                "type": "pose.tracking", "visible": True, "source": "simulator",
            }, tracking=True)
            await send_and_expect({
                "type": "gesture.recognized", "name": "swipe_right", "source": "simulator",
            }, last_gesture="swipe_right")
            await send_and_expect({
                "type": "lighting.changed", "level": "low", "source": "simulator",
            }, lighting="low")
            print_progress("PASS: Camera, skeleton, gesture and lighting events reach React")

            rejected = await tcp_event({
                "type": "pose.tracking", "visible": "false", "source": "simulator",
            }, host, tcp_port, timeout)
            if rejected.get("ok") is not False:
                raise ProbeFailure("Invalid sensor Boolean was not rejected")
            # The invalid TCP event must not broadcast or mutate state.
            try:
                unwanted = await asyncio.wait_for(ws.recv(), min(timeout, 0.15))
            except asyncio.TimeoutError:
                pass
            else:
                raise ProbeFailure(f"Invalid event unexpectedly broadcast: {unwanted!r}")
            print_progress("PASS: Malformed sensor event is rejected without a state broadcast")

            await ws.send(json.dumps({
                "type": "command", "action": "mode.selected", "payload": {"mode": "gaze"},
            }))
            assert_state(await ws_message(ws, timeout), mode="gaze", event_source="ui_bridge")
            await ws.send(json.dumps({
                "type": "command", "action": "game.restart", "payload": {},
            }))
            assert_state(await ws_message(ws, timeout), mode="gaze", question_index=0)
            print_progress("PASS: Browser mode and restart commands reach Python")
        finally:
            # Clean up *our* device and interaction state for the next manual demo.
            # If a real sensor is active at the same time, it may change state again.
            await send_and_expect({
                "type": "device.lost", "source": "simulator",
            }, level="guest", user_id="guest")
            await send_and_expect({
                "type": "camera.status", "ready": False, "source": "simulator",
            }, camera_ready=False)
            await send_and_expect({
                "type": "pose.tracking", "visible": False, "source": "simulator",
            }, tracking=False)
            await send_and_expect({
                "type": "lighting.changed", "level": "unknown", "source": "simulator",
            }, lighting="unknown")
            await ws.send(json.dumps({
                "type": "command", "action": "mode.selected", "payload": {"mode": "gesture"},
            }))
            assert_state(await ws_message(ws, timeout), mode="gesture")
            await ws.send(json.dumps({
                "type": "command", "action": "game.restart", "payload": {},
            }))
            assert_state(await ws_message(ws, timeout), question_index=0, level="guest")
            print_progress("PASS: Demo session returned to guest/gesture baseline")
    print_progress("ALL INTEGRATION SMOKE CHECKS PASSED (SIMULATED EVENTS)")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--tcp-port", type=int, default=8765)
    parser.add_argument("--ws-port", type=int, default=8766)
    args = parser.parse_args()
    try:
        asyncio.run(probe(args.host, args.tcp_port, args.ws_port))
    except (ProbeFailure, ConnectionError, OSError, TimeoutError) as exc:
        print(f"INTEGRATION SMOKE FAILED: {exc}", file=sys.stderr)
        print("Check that exactly one Python backend is running on 8765/8766.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
