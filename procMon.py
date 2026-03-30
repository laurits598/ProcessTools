# requirements:
# pip install textual psutil requests

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Header, Footer, Input, Static
from textual.containers import Container, Horizontal
from textual.reactive import reactive
from textual.coordinate import Coordinate

import psutil
from datetime import datetime
import subprocess
import requests
import os


API_KEY = "6a39523a8dc3314d773b74d7ed1cdca9f2901503445e3bdd6707aa12a903cf373f6a2115a7b1c20b"

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
        ("c", "copy_cell", "Copy"),
        ("q", "quit", "Quit"),
        ("a", "abuse_check", "Check IP"),
        ("b", "back", "Back"),
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
        self.showing_abuse = False
        self.set_interval(self.refresh_interval, self.update_table)

    def on_input_changed(self, event: Input.Changed) -> None:
        self.filter_text = event.value.lower()

    # --------------------
    # COPY
    # --------------------
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

    # --------------------
    # ABUSE CHECK
    # --------------------
    def action_abuse_check(self) -> None:
        if self.table.cursor_coordinate is None:
            return

        coord = self.table.cursor_coordinate
        remote = str(self.table.get_cell_at((coord.row, 4)))
        ip = remote.split(":")[0]

        self.status.update(f"🔄 Fetching abuse data for {ip}...")

        # run in background thread
        self.run_worker(lambda: self.fetch_abuse(ip), exclusive=True, thread=True)
    def fetch_abuse(self, ip: str):
        try:
            headers = {
                "Key": API_KEY,
                "Accept": "application/json"
            }

            params = {
                "ipAddress": ip,
                "maxAgeInDays": 90,
                "verbose": ""
            }

            response = requests.get(
                "https://api.abuseipdb.com/api/v2/check",
                headers=headers,
                params=params,
                timeout=10
            )

            json_data = response.json()

            if "data" not in json_data:
                error_msg = json_data.get("errors", [{"detail": "Unknown error"}])[0]["detail"]
                self.call_from_thread(
                    self.status.update,
                    f"API Error: {error_msg}"
                )
                return

            data = json_data["data"]

            def update_ui():
                self.table.clear(columns=True)
                self.table.add_columns("Field", "Value")

                def add(field, value):
                    self.table.add_row(field, str(value))

                add("IP", data.get("ipAddress"))
                add("Country", f"{data.get('countryName')} ({data.get('countryCode')})")
                add("ISP", data.get("isp"))
                add("Domain", data.get("domain"))
                add("Usage", data.get("usageType"))
                add("Score", data.get("abuseConfidenceScore"))
                add("Reports", data.get("totalReports"))
                add("Distinct Users", data.get("numDistinctUsers"))
                add("Last Report", data.get("lastReportedAt"))
                add("Tor", data.get("isTor"))
                add("Whitelisted", data.get("isWhitelisted"))

                reports = data.get("reports", [])
                if reports:
                    self.table.add_row("---- Reports ----", "")
                    for r in reports[:5]:
                        self.table.add_row(
                            "Report",
                            f"{r.get('reportedAt')} | {r.get('comment')}"
                        )

                self.showing_abuse = True
                self.status.update(f"Abuse info for {ip} (press b to go back)")

            self.call_from_thread(update_ui)

        except Exception as e:
            self.call_from_thread(
                self.status.update,
                f"Error: {e}"
            )

    # --------------------
    # BACK
    # --------------------
    def action_back(self) -> None:
        if self.showing_abuse:
            self.showing_abuse = False

            self.table.clear(columns=True)
            self.table.add_columns(
                "Time", "PID", "Process", "Local", "Remote", "Status"
            )

            self.update_table()

    # --------------------
    # MAIN TABLE
    # --------------------
    def update_table(self) -> None:
        if self.showing_abuse:
            return

        saved_coord = self.table.cursor_coordinate
        saved_scroll = self.table.scroll_y

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

        # restore cursor
        if saved_coord is not None:
            try:
                max_row = len(rows) - 1
                row = min(saved_coord.row, max_row) if max_row >= 0 else 0
                self.table.cursor_coordinate = Coordinate(row, saved_coord.column)
            except Exception:
                pass

        # restore scroll
        try:
            self.table.scroll_to(y=saved_scroll, animate=False)
        except Exception:
            pass

        self.status.update(
            f"Connections: {len(rows)} | Filter: {self.filter_text or 'None'}"
        )


if __name__ == "__main__":
    app = ConnectionMonitor()
    app.run()
