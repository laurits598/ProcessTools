#!/usr/bin/env python3

# requirements:
# pip install textual psutil

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer, Static
from textual.containers import Container
from textual.reactive import reactive
import psutil
from datetime import datetime
from textual.coordinate import Coordinate
import os
import signal


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
            "Time", "PID", "Process", "CPU %", "Memory MB"
        )

        self.status = Static("Running")

        yield Container(self.table)
        yield self.status
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(self.refresh_interval, self.update_table)

    def action_kill_process(self) -> None:
        if self.table.cursor_coordinate is None:
            return

        try:
            coord = self.table.cursor_coordinate

            # PID is column 1
            pid = int(self.table.get_cell_at((coord.row, 1)))

            os.kill(pid, signal.SIGTERM)
            self.status.update(f"Killed PID {pid}")

        except Exception as e:
            self.status.update(f"Kill failed: {e}")

    def update_table(self) -> None:
        # Save current cursor position
        saved_coord = self.table.cursor_coordinate

        self.table.clear()
        now = datetime.now().strftime("%H:%M:%S")

        processes = []

        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_info']):
            try:
                cpu = proc.info['cpu_percent']
                mem = proc.info['memory_info'].rss / (1024 * 1024)

                processes.append((
                    cpu,
                    mem,
                    proc.info['pid'],
                    proc.info['name'] or "?"
                ))

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        processes.sort(key=lambda x: (x[0], x[1]), reverse=True)

        for cpu, mem, pid, name in processes:
            self.table.add_row(
                now,
                str(pid),
                name,
                f"{cpu:.1f}",
                f"{mem:.1f}"
            )

        # Restore cursor position if possible
        if saved_coord is not None:
            try:
                max_row = len(processes) - 1
                row = min(saved_coord.row, max_row) if max_row >= 0 else 0
                col = saved_coord.column
                self.table.cursor_coordinate = Coordinate(row, col)
            except Exception:
                pass

        self.status.update(f"Processes: {len(processes)}")


if __name__ == "__main__":
    app = ProcUsage()
    app.run()
