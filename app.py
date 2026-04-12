import os
import re
import sys
import random
import shutil
import time
import threading
import tkinter as tk
from tkinter import filedialog
from flask import Flask, render_template, request, jsonify, send_from_directory, abort


def resource_path(relative):
    """Get absolute path to resource, works for dev and for PyInstaller."""
    if getattr(sys, "_MEIPASS", None):
        return os.path.join(sys._MEIPASS, relative)
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative)


app = Flask(
    __name__,
    template_folder=resource_path("templates"),
    static_folder=resource_path("static"),
)

ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}

SHUTDOWN_TIMEOUT = 120  # seconds without a heartbeat before auto-exit
_last_heartbeat = time.time()
_heartbeat_lock = threading.Lock()
_tab_count = 0
_tab_lock = threading.Lock()

state = {
    "folder": None,
    "champion": None,
    "challenger": None,
    "pending": [],
    "total": 0,
}
history = []


def is_safe_path(base, filename):
    """Prevent path traversal by ensuring the resolved path stays within base."""
    base = os.path.abspath(base)
    target = os.path.abspath(os.path.join(base, filename))
    return target.startswith(base + os.sep) or target == base


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/load", methods=["POST"])
def load_folder():
    data = request.get_json()
    folder = data.get("folder", "").strip()

    if not folder or not os.path.isdir(folder):
        return jsonify({"error": "Invalid folder path."}), 400

    folder = os.path.abspath(folder)

    # Format filter
    formats = data.get("formats", None)
    if formats and isinstance(formats, list):
        exts = {e.lower() for e in formats if isinstance(e, str) and e.startswith(".")}
    else:
        exts = ALLOWED_EXTENSIONS
    # Only allow known extensions
    exts = exts & ALLOWED_EXTENSIONS
    if not exts:
        exts = ALLOWED_EXTENSIONS

    images = sorted(
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
        and os.path.splitext(f)[1].lower() in exts
    )

    # Filename filter
    filter_text = data.get("filterText", "").strip()
    filter_mode = data.get("filterMode", "")
    if filter_text:
        if filter_mode == "starts":
            images = [f for f in images if os.path.splitext(f)[0].lower().startswith(filter_text.lower())]
        elif filter_mode == "contains":
            images = [f for f in images if filter_text.lower() in os.path.splitext(f)[0].lower()]
        elif filter_mode == "ends":
            images = [f for f in images if os.path.splitext(f)[0].lower().endswith(filter_text.lower())]
        elif filter_mode == "regex":
            try:
                pat = re.compile(filter_text, re.IGNORECASE)
                images = [f for f in images if pat.search(os.path.splitext(f)[0])]
            except re.error:
                return jsonify({"error": "Invalid regex pattern."}), 400

    if len(images) == 0:
        return jsonify({"error": "No supported images found matching the filters."}), 400

    if len(images) == 1:
        state["folder"] = folder
        state["champion"] = images[0]
        state["challenger"] = None
        state["pending"] = []
        state["total"] = 1
        return jsonify({
            "status": "done",
            "winner": images[0],
            "total": 1,
        })

    state["folder"] = folder
    state["champion"] = images[0]
    state["challenger"] = images[1]
    state["pending"] = images[2:]
    state["total"] = len(images)
    history.clear()

    return jsonify({
        "status": "continue",
        "champion": images[0],
        "challenger": images[1],
        "remaining": len(state["pending"]),
        "total": state["total"],
    })


@app.route("/api/browse", methods=["POST"])
def browse_folder():
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    folder = filedialog.askdirectory(title="Select image folder")
    root.destroy()
    if not folder:
        return jsonify({"folder": ""})
    return jsonify({"folder": os.path.normpath(folder)})


@app.route("/api/image/<path:filename>")
def serve_image(filename):
    if state["folder"] is None:
        abort(404)
    if not is_safe_path(state["folder"], filename):
        abort(403)
    return send_from_directory(state["folder"], filename)


@app.route("/api/choose", methods=["POST"])
def choose_winner():
    data = request.get_json()
    winner = data.get("winner", "")

    if winner not in (state["champion"], state["challenger"]):
        return jsonify({"error": "Invalid winner."}), 400

    # Save snapshot for undo
    history.append({
        "champion": state["champion"],
        "challenger": state["challenger"],
        "pending": list(state["pending"]),
    })

    state["champion"] = winner

    if not state["pending"]:
        state["challenger"] = None
        return jsonify({
            "status": "done",
            "winner": state["champion"],
            "canUndo": len(history) > 0,
        })

    state["challenger"] = state["pending"].pop(0)

    return jsonify({
        "status": "continue",
        "champion": state["champion"],
        "challenger": state["challenger"],
        "remaining": len(state["pending"]),
        "total": state["total"],
        "canUndo": len(history) > 0,
    })


@app.route("/api/back-to-pile", methods=["POST"])
def back_to_pile():
    data = request.get_json()
    image = data.get("image", "")

    if image not in (state["champion"], state["challenger"]):
        return jsonify({"error": "Invalid image."}), 400

    if not state["pending"] and state["champion"] and state["challenger"]:
        # Only two images left — sending one back just re-shows the same pair
        pass

    # Save snapshot for undo
    history.append({
        "champion": state["champion"],
        "challenger": state["challenger"],
        "pending": list(state["pending"]),
    })

    # The other image stays as champion; the sent-back image goes to end of pending
    other = state["challenger"] if image == state["champion"] else state["champion"]
    state["pending"].append(image)
    state["champion"] = other
    state["challenger"] = state["pending"].pop(0)

    return jsonify({
        "status": "continue",
        "champion": state["champion"],
        "challenger": state["challenger"],
        "remaining": len(state["pending"]),
        "total": state["total"],
        "canUndo": len(history) > 0,
    })


@app.route("/api/undo", methods=["POST"])
def undo_choice():
    if not history:
        return jsonify({"error": "Nothing to undo."}), 400

    snapshot = history.pop()
    state["champion"] = snapshot["champion"]
    state["challenger"] = snapshot["challenger"]
    state["pending"] = snapshot["pending"]

    return jsonify({
        "status": "continue",
        "champion": state["champion"],
        "challenger": state["challenger"],
        "remaining": len(state["pending"]),
        "total": state["total"],
        "canUndo": len(history) > 0,
    })


@app.route("/api/keep", methods=["POST"])
def keep_winner():
    if state["folder"] is None or state["champion"] is None:
        return jsonify({"error": "No winner to keep."}), 400

    filename = state["champion"]
    if not is_safe_path(state["folder"], filename):
        return jsonify({"error": "Invalid filename."}), 403

    src = os.path.join(state["folder"], filename)
    keep_dir = os.path.join(state["folder"], "keep")
    os.makedirs(keep_dir, exist_ok=True)
    dest = os.path.join(keep_dir, filename)

    if os.path.exists(dest):
        return jsonify({"error": "File already exists in keep folder."}), 409

    shutil.copy2(src, dest)
    return jsonify({"ok": True})


@app.route("/api/heartbeat", methods=["POST"])
def heartbeat():
    global _last_heartbeat
    with _heartbeat_lock:
        _last_heartbeat = time.time()
    return "", 204


@app.route("/api/connect", methods=["POST"])
def tab_connect():
    global _tab_count
    with _tab_lock:
        _tab_count += 1
    return "", 204


@app.route("/api/disconnect", methods=["POST"])
def tab_disconnect():
    global _tab_count
    with _tab_lock:
        _tab_count = max(0, _tab_count - 1)
        if _tab_count == 0:
            # Last tab closed — shut down after a grace period to allow reopening
            threading.Timer(15.0, _shutdown_if_no_tabs).start()
    return "", 204


def _shutdown_if_no_tabs():
    with _tab_lock:
        if _tab_count == 0:
            os._exit(0)


@app.route("/api/shutdown", methods=["POST"])
def shutdown():
    os._exit(0)


def _watchdog():
    """Background thread that exits the process after SHUTDOWN_TIMEOUT of inactivity."""
    while True:
        time.sleep(3)
        with _heartbeat_lock:
            elapsed = time.time() - _last_heartbeat
        if elapsed > SHUTDOWN_TIMEOUT:
            os._exit(0)


if __name__ == "__main__":
    import webbrowser, socket

    def port_in_use(port):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            return s.connect_ex(("127.0.0.1", port)) == 0

    is_frozen = getattr(sys, "frozen", False)
    is_reloader = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if not is_reloader:
        if port_in_use(5000):
            # Another instance is already running — just open the browser to it
            webbrowser.open("http://127.0.0.1:5000")
            sys.exit(0)
        threading.Timer(1.5, lambda: webbrowser.open("http://127.0.0.1:5000")).start()

    if is_frozen:
        threading.Thread(target=_watchdog, daemon=True).start()
    app.run(debug=not is_frozen, port=5000)
