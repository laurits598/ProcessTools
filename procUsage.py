#!/usr/bin/env python3

# requirements:
# pip install textual psutil

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer, Static
from textual.containers import Container
from textual.coordinate import Coordinate

import psutil
from datetime import datetime
import os
import signal


# --------------------
# SAFETY CLASSIFICATION
# --------------------
def classify_safety(pid, name):
    name = (name or "").lower()

    critical_names = [
        "systemd", "init", "kernel", "csrss", "wininit",
        "services", "lsass", "smss"
    ]

    important_names = [
        "explorer", "bash", "zsh", "powershell", "ssh"
    ]

    if pid in (0, 1):
        return "🔴 Critical"

    if name in critical_names:
        return "🔴 Critical"

    if name in important_names:
        return "🟡 Important"

    return "🟢 Safe"


# --------------------
# TYPE CLASSIFICATION
# --------------------
def classify_type(pid, name):
    name = (name or "").lower()

    if pid in (0, 1):
        return "🧠 Kernel"

    if name in ["systemd", "init", "wininit", "csrss", "services", "lsass"]:
        return "⚙️ System"

    if any(x in name for x in ["ssh", "network", "dhclient"]):
        return "🌐 Network"

    if any(x in name for x in ["service", "daemon"]):
        return "🔧 Service"

    if any(x in name for x in ["chrome", "firefox", "code", "python", "node"]):
        return "🖥️ Application"

    return "🖥️ Application"


class ProcUsage(App):
    CSS = """
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("k", "kill_process", "Kill process"),
        ("q", "quit", "Quit"),
    ]

    refresh_interval = 2

    def compose(self) -> ComposeResult:
        yield Header()

        self.table = DataTable(zebra_stripes=True)
        self.table.cursor_type = "cell"
        self.table.add_columns(
            "Time", "PID", "Process", "CPU %", "Memory MB", "Safety", "Type"
        )

        self.status = Static("Running")

        yield Container(self.table)
        yield self.status
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(self.refresh_interval, self.update_table)

    # --------------------
    # KILL (SAFE)
    # --------------------
    def action_kill_process(self) -> None:
        if self.table.cursor_coordinate is None:
            return

        try:
            coord = self.table.cursor_coordinate

            pid = int(self.table.get_cell_at((coord.row, 1)))
            level = str(self.table.get_cell_at((coord.row, 5)))

            if "Critical" in level:
                self.status.update("🚫 Refusing to kill CRITICAL process")
                return

            os.kill(pid, signal.SIGTERM)

            self.status.update(f"Killed PID {pid}")

        except Exception as e:
            self.status.update(f"Kill failed: {e}")

    # --------------------
    # MAIN LOOP
    # --------------------
    def update_table(self) -> None:
        saved_coord = self.table.cursor_coordinate

        self.table.clear()
        now = datetime.now().strftime("%H:%M:%S")

        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                pid = proc.info['pid']
                name = proc.info['name'] or "?"

                cpu = proc.info['cpu_percent']
                mem = proc.info['memory_info'].rss / (1024 * 1024)

                safety = classify_safety(pid, name)
                ptype = classify_type(pid, name)

                processes.append((
                    cpu,
                    mem,
                    pid,
                    name,
                    safety,
                    ptype
                ))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(key=lambda x: (x[0], x[1]), reverse=True)

        for cpu, mem, pid, name, safety, ptype in processes:
            self.table.add_row(
                now,
                str(pid),
                name,
                f"{cpu:.1f}",
                f"{mem:.1f}",
                safety,
                ptype
            )

        # restore cursor
        if saved_coord is not None:
            try:
                max_row = len(processes) - 1
                row = min(saved_coord.row, max_row) if max_row >= 0 else 0
                self.table.cursor_coordinate = Coordinate(row, saved_coord.column)
            except Exception:
                pass

        self.status.update(f"Processes: {len(processes)}")


if __name__ == "__main__":
    app = ProcUsage()
    app.run()
