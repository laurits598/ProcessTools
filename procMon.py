# requirements:
# pip install textual psutil

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer, Input, Static
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.coordinate import Coordinate
import psutil
from datetime import datetime
import subprocess


class ConnectionMonitor(App):
    CSS = """
    Screen {
        layout: vertical;
    }
    #controls {
        height: 3;
    }
    Input {
        width: 40%;
        margin: 0 1;
    }
    DataTable {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("c", "copy_cell", "Copy cell"),
        ("q", "quit", "Quit"),
    ]

    refresh_interval = 2
    filter_text = reactive("")

    def compose(self) -> ComposeResult:
        yield Header()

        with Horizontal(id="controls"):
            self.filter_input = Input(placeholder="Filter by process / IP / port...")
            self.status = Static("Running")
            yield self.filter_input
            yield self.status

        self.table = DataTable(zebra_stripes=True)
        self.table.cursor_type = "cell"
        self.table.add_columns(
            "Time", "PID", "Process", "Local", "Remote", "Status"
        )

        yield Container(self.table)
        yield Footer()

    def on_mount(self) -> None:
        self.set_interval(self.refresh_interval, self.update_table)

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value.lower()

    # Clipboard (WSL-safe)
    def action_copy_cell(self) -> None:
        if self.table.cursor_coordinate is None:
            return

        try:
            coord = self.table.cursor_coordinate
            value = str(self.table.get_cell_at(coord))

            subprocess.run(
                ["clip.exe"],
                input=value.encode(),
                check=True
            )

            self.status.update(f"Copied: {value}")

        except Exception as e:
            self.status.update(f"Copy failed: {e}")

    def update_table(self) -> None:
        # Save cursor
        saved_coord = self.table.cursor_coordinate

        self.table.clear()
        now = datetime.now().strftime("%H:%M:%S")

        try:
            connections = psutil.net_connections(kind='inet')
        except Exception as e:
            self.status.update(f"Error: {e}")
            return

        rows = []

        for conn in connections:
            if not conn.raddr:
                continue

            pid = conn.pid
            proc_name = "?"

            if pid:
                try:
                    proc_name = psutil.Process(pid).name()
                except Exception:
                    pass

            local = f"{conn.laddr.ip}:{conn.laddr.port}" if conn.laddr else "?"
            remote = f"{conn.raddr.ip}:{conn.raddr.port}" if conn.raddr else "?"

            row_text = f"{proc_name} {local} {remote}"

            if self.filter_text and self.filter_text not in row_text.lower():
                continue

            rows.append((
                now,
                str(pid or "-"),
                proc_name,
                local,
                remote,
                conn.status
            ))

        rows.reverse()

        for row in rows:
            self.table.add_row(*row)

        # Restore cursor
        if saved_coord is not None:
            try:
                max_row = len(rows) - 1
                row = min(saved_coord.row, max_row) if max_row >= 0 else 0
                col = saved_coord.column
                self.table.cursor_coordinate = Coordinate(row, col)
            except Exception:
                pass

        self.status.update(
            f"Connections: {len(rows)} | Filter: {self.filter_text or 'None'}"
        )


if __name__ == "__main__":
    app = ConnectionMonitor()
    app.run()
