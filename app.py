import os
import sys
import random
import time
import threading
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

    images = sorted(
        f for f in os.listdir(folder)
        if os.path.isfile(os.path.join(folder, f))
        and os.path.splitext(f)[1].lower() in ALLOWED_EXTENSIONS
    )

    if len(images) == 0:
        return jsonify({"error": "No supported images found in that folder."}), 400

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

    return jsonify({
        "status": "continue",
        "champion": images[0],
        "challenger": images[1],
        "remaining": len(state["pending"]),
        "total": state["total"],
    })


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

    state["champion"] = winner

    if not state["pending"]:
        return jsonify({
            "status": "done",
            "winner": state["champion"],
        })

    state["challenger"] = state["pending"].pop(0)

    return jsonify({
        "status": "continue",
        "champion": state["champion"],
        "challenger": state["challenger"],
        "remaining": len(state["pending"]),
        "total": state["total"],
    })


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
            # Last tab closed — shut down after a brief grace period
            threading.Timer(1.0, _shutdown_if_no_tabs).start()
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
