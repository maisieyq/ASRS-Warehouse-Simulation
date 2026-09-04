import os
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path

from streamlit.web import cli as stcli


def get_base_path() -> Path:
    """
    Return the correct application folder.

    Normal Python:
        project folder

    PyInstaller:
        temporary bundled application folder
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent


def find_available_port(
    start_port: int = 8501,
    end_port: int = 8510,
) -> int:
    """
    Find an available local port for Streamlit.
    """
    for port in range(start_port, end_port + 1):
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as sock:
            result = sock.connect_ex(
                ("127.0.0.1", port)
            )

            if result != 0:
                return port

    raise RuntimeError(
        "No available port found between "
        f"{start_port} and {end_port}."
    )


def open_browser(port: int) -> None:
    """
    Wait briefly for Streamlit to start,
    then open the dashboard.
    """
    time.sleep(2.5)

    webbrowser.open(
        f"http://127.0.0.1:{port}"
    )


def main() -> None:
    os.environ["STREAMLIT_GLOBAL_DEVELOPMENT_MODE"] = "false"
    base_path = get_base_path()

    app_path = base_path / "app.py"

    if not app_path.exists():
        raise FileNotFoundError(
            f"Cannot find Streamlit application: "
            f"{app_path}"
        )

    port = find_available_port()

    browser_thread = threading.Thread(
        target=open_browser,
        args=(port,),
        daemon=True,
    )

    browser_thread.start()

    sys.argv = [
        "streamlit",
        "run",
        str(app_path),
        "--global.developmentMode=false",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--server.fileWatcherType=none",
        "--browser.gatherUsageStats=false",
    ]

    stcli.main()


if __name__ == "__main__":
    main()