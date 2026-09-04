import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import webview
from streamlit.web import cli as stcli


APP_TITLE = "AS/RS Warehouse Simulation"


def get_base_path() -> Path:
    """
    Return the application resource folder.

    Normal Python:
        Project folder

    PyInstaller:
        Temporary extracted application folder
    """
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS)

    return Path(__file__).resolve().parent


def find_available_port(
    start_port: int = 8501,
    end_port: int = 8510,
) -> int:
    """
    Find an available localhost port.
    """
    for port in range(
        start_port,
        end_port + 1,
    ):
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
        "No available local port was found."
    )


def wait_for_server(
    port: int,
    timeout: float = 30.0,
) -> bool:
    """
    Wait until the Streamlit server is ready.
    """
    start_time = time.time()

    while (
        time.time() - start_time
        < timeout
    ):
        with socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM,
        ) as sock:

            result = sock.connect_ex(
                ("127.0.0.1", port)
            )

            if result == 0:
                return True

        time.sleep(0.2)

    return False


def run_streamlit_child(
    app_path: Path,
    port: int,
) -> None:
    """
    Run Streamlit in the main thread of
    a separate child process.
    """
    os.environ[
        "STREAMLIT_GLOBAL_DEVELOPMENT_MODE"
    ] = "false"

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


def start_streamlit_process(
    app_path: Path,
    port: int,
) -> subprocess.Popen:
    """
    Start Streamlit as a separate process.

    In development:
        python launcher.py --streamlit-child ...

    In PyInstaller EXE:
        ASRS_Warehouse_Simulation.exe
        --streamlit-child ...
    """

    if getattr(sys, "frozen", False):
        command = [
            sys.executable,
            "--streamlit-child",
            str(app_path),
            str(port),
        ]

    else:
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--streamlit-child",
            str(app_path),
            str(port),
        ]

    kwargs = {}

    if os.name == "nt":
        kwargs["creationflags"] = (
            subprocess.CREATE_NO_WINDOW
        )

    return subprocess.Popen(
        command,
        **kwargs,
    )


def stop_process_tree(
    process: subprocess.Popen,
) -> None:
    """
    Stop Streamlit and its child processes.
    """
    if process.poll() is not None:
        return

    if os.name == "nt":
        subprocess.run(
            [
                "taskkill",
                "/PID",
                str(process.pid),
                "/T",
                "/F",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(
                subprocess.CREATE_NO_WINDOW
            ),
        )

    else:
        process.terminate()

        try:
            process.wait(timeout=5)

        except subprocess.TimeoutExpired:
            process.kill()


def main() -> None:

    # =========================================
    # STREAMLIT CHILD PROCESS MODE
    # =========================================

    if (
        len(sys.argv) >= 4
        and sys.argv[1]
        == "--streamlit-child"
    ):
        app_path = Path(sys.argv[2])
        port = int(sys.argv[3])

        run_streamlit_child(
            app_path,
            port,
        )

        return


    # =========================================
    # MAIN DESKTOP APPLICATION MODE
    # =========================================

    base_path = get_base_path()

    app_path = (
        base_path
        / "app.py"
    )

    if not app_path.exists():
        raise FileNotFoundError(
            "Cannot find app.py at: "
            f"{app_path}"
        )

    os.chdir(base_path)

    port = find_available_port()

    streamlit_process = (
        start_streamlit_process(
            app_path,
            port,
        )
    )

    try:
        if not wait_for_server(
            port,
            timeout=30,
        ):
            raise RuntimeError(
                "The AS/RS Streamlit server "
                "could not be started."
            )

        local_url = (
            f"http://127.0.0.1:{port}"
        )

        webview.create_window(
            title=APP_TITLE,
            url=local_url,
            width=1400,
            height=900,
            resizable=True,
        )

        # This remains active until
        # the user closes the window.
        webview.start()

    finally:
        # When the PyWebView window is closed,
        # terminate Streamlit completely.
        stop_process_tree(
            streamlit_process
        )


if __name__ == "__main__":
    main()