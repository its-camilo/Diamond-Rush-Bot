"""Record manual Diamond Rush arrow-key input as a compact route log.

Run this in a separate PowerShell window while playing manually. Only arrow
keys pressed after F8 are recorded; F10 stops and saves the capture.
"""
import argparse
from datetime import datetime
import json
from pathlib import Path
import time


_DIRECTION_LETTERS = {
    "up": "U",
    "down": "D",
    "left": "L",
    "right": "R",
}


def format_sequence(events):
    """Collapse adjacent direction events into notation such as ``UU R DDD``."""
    letters = []
    for event in events:
        direction = event if isinstance(event, str) else event.get("direction", "")
        letter = _DIRECTION_LETTERS.get(str(direction).lower())
        if letter:
            letters.append(letter)
    if not letters:
        return ""

    groups = []
    current = letters[0]
    count = 1
    for letter in letters[1:]:
        if letter == current:
            count += 1
        else:
            groups.append(current * count)
            current = letter
            count = 1
    groups.append(current * count)
    return " ".join(groups)


def record_route(output_path=None):
    """Listen for arrow-key presses locally until F10 and save JSON + sequence."""
    try:
        from pynput import keyboard
    except ImportError as exc:
        raise RuntimeError("Falta pynput; instala con: pip install pynput") from exc

    if output_path is None:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        output_path = Path("route-captures") / f"route-{stamp}.json"
    else:
        output_path = Path(output_path)

    keys = {
        keyboard.Key.up: "up",
        keyboard.Key.down: "down",
        keyboard.Key.left: "left",
        keyboard.Key.right: "right",
    }
    events = []
    pressed = {}
    recording_started = None

    print("Grabador listo. Enfoca el juego y pulsa F8 para empezar; F10 guarda y termina.")
    print("Solo se guardan flechas; usa pulsaciones cortas para contar pasos de una casilla.")

    def on_press(key):
        nonlocal recording_started
        now = time.monotonic()
        if key == keyboard.Key.f8:
            if recording_started is None:
                recording_started = now
                print("Grabando flechas...")
            return
        if key == keyboard.Key.f10:
            return False
        direction = keys.get(key)
        if recording_started is None or direction is None or key in pressed:
            return
        event = {
            "direction": direction,
            "at_ms": round((now - recording_started) * 1000),
            "held_ms": None,
        }
        events.append(event)
        pressed[key] = (event, now)

    def on_release(key):
        held = pressed.pop(key, None)
        if held is not None:
            event, down_at = held
            event["held_ms"] = round((time.monotonic() - down_at) * 1000)

    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()

    stopped_at = time.monotonic()
    for event, down_at in pressed.values():
        event["held_ms"] = round((stopped_at - down_at) * 1000)

    sequence = format_sequence(events)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "recorded_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "sequence": sequence,
        "events": events,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Guardado: {output_path}")
    print(f"Secuencia: {sequence or '(sin flechas)'}")
    return output_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", help="Ruta JSON de salida (opcional)")
    args = parser.parse_args()
    try:
        record_route(args.output)
    except RuntimeError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
