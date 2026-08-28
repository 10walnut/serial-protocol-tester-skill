#!/usr/bin/env python3
"""PySide6 serial protocol console for serial_protocol.v1 scripts."""

from __future__ import annotations

import base64
import json
import struct
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import serial
    from serial.tools import list_ports
except ImportError as exc:  # pragma: no cover - user-facing startup guard
    raise SystemExit("pyserial is required. Install with: pip install -r requirements.txt") from exc

try:
    from PySide6.QtCore import QTimer, Qt
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import (
        QApplication,
        QComboBox,
        QFileDialog,
        QGridLayout,
        QGroupBox,
        QHBoxLayout,
        QHeaderView,
        QLabel,
        QLineEdit,
        QMainWindow,
        QMessageBox,
        QPushButton,
        QSpinBox,
        QSplitter,
        QTableWidget,
        QTableWidgetItem,
        QTextEdit,
        QVBoxLayout,
        QWidget,
    )
except ImportError as exc:  # pragma: no cover - user-facing startup guard
    raise SystemExit("PySide6 is required. Install with: pip install -r requirements.txt") from exc


def resource_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root)
    return Path(__file__).resolve().parent


ROOT = resource_root()
SAMPLE_PROTOCOL = ROOT / "sample_protocol.json"


def now() -> str:
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def normalize_hex(text: str) -> str:
    cleaned = text.replace("0x", "").replace("0X", "")
    for ch in ",:-":
        cleaned = cleaned.replace(ch, " ")
    return " ".join(cleaned.split()).upper()


def bytes_to_hex(data: bytes) -> str:
    return " ".join(f"{byte:02X}" for byte in data)


def payload_to_bytes(payload: dict[str, Any]) -> bytes:
    mode = payload.get("mode", "hex")
    data = str(payload.get("data", ""))
    terminator = str(payload.get("terminator", ""))

    if mode == "hex":
        body = bytes.fromhex(normalize_hex(data))
    elif mode in {"text", "utf8"}:
        body = data.encode("utf-8")
    elif mode == "ascii":
        body = data.encode("ascii")
    elif mode == "base64":
        body = base64.b64decode(data.encode("ascii"), validate=True)
    else:
        raise ValueError(f"Unsupported payload mode: {mode}")

    if terminator:
        if terminator.startswith("\\x"):
            body += bytes.fromhex(terminator.replace("\\x", ""))
        elif terminator.lower() in {"crlf", "\\r\\n"}:
            body += b"\r\n"
        elif terminator.lower() in {"lf", "\\n"}:
            body += b"\n"
        elif terminator.lower() in {"cr", "\\r"}:
            body += b"\r"
        else:
            body += terminator.encode("utf-8")
    return body


def display_payload(data: bytes, mode: str = "hex") -> str:
    if mode == "hex":
        return bytes_to_hex(data)
    if mode == "ascii":
        return data.decode("ascii", errors="replace")
    if mode in {"text", "utf8"}:
        return data.decode("utf-8", errors="replace")
    if mode == "base64":
        return base64.b64encode(data).decode("ascii")
    return bytes_to_hex(data)


def command_reply_bytes(command: dict[str, Any]) -> bytes | None:
    auto_reply = command.get("auto_reply", {})
    response = command.get("response", {})
    mode = response.get("mode", command.get("request", {}).get("mode", "hex"))

    if auto_reply.get("enabled") is True and "data" in auto_reply:
        return payload_to_bytes({"mode": mode, "data": auto_reply["data"]})
    if "example" in response:
        return payload_to_bytes({"mode": mode, "data": response["example"]})
    return None


def decode_fields(data: bytes, command: dict[str, Any]) -> str:
    response = command.get("response") or {}
    rules = response.get("decode") or []
    if not rules:
        return ""

    decoded: list[str] = []
    for rule in rules:
        label = rule.get("label") or rule.get("name") or "value"
        dtype = rule.get("type", "hex")
        offset = int(rule.get("offset", 0))
        length = int(rule.get("length", default_length(dtype)))
        if length == 0:
            length = max(0, len(data) - offset)
        chunk = data[offset : offset + length]
        if len(chunk) < length:
            decoded.append(f"{label}=<short frame>")
            continue

        try:
            value = decode_value(chunk, dtype, rule)
        except Exception as exc:  # noqa: BLE001 - show decode failures in UI
            value = f"<decode error: {exc}>"
        decoded.append(f"{label}={value}")

    return "; ".join(decoded)


def default_length(dtype: str) -> int:
    return {
        "uint8": 1,
        "int8": 1,
        "uint16": 2,
        "int16": 2,
        "uint32": 4,
        "int32": 4,
        "float32": 4,
    }.get(dtype, 0)


def decode_value(chunk: bytes, dtype: str, rule: dict[str, Any]) -> str:
    endian = "<" if rule.get("endian", "big") == "little" else ">"
    formats = {
        "uint8": "B",
        "int8": "b",
        "uint16": "H",
        "int16": "h",
        "uint32": "I",
        "int32": "i",
        "float32": "f",
    }

    if dtype in formats:
        raw = struct.unpack(endian + formats[dtype], chunk)[0]
        value = raw * float(rule.get("scale", 1)) + float(rule.get("offset_value", 0))
        unit = rule.get("unit", "")
        return f"{value:g}{unit}"
    if dtype in {"bytes", "hex"}:
        return bytes_to_hex(chunk)
    if dtype == "ascii":
        return chunk.decode("ascii", errors="replace")
    if dtype == "utf8":
        return chunk.decode("utf-8", errors="replace")
    return bytes_to_hex(chunk)


@dataclass
class SerialSettings:
    baudrate: int = 115200
    bytesize: int = 8
    parity: str = "N"
    stopbits: float = 1
    timeout: float = 0


class SerialConsole(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Serial Protocol Tester")
        self.resize(1280, 760)

        self.protocol: dict[str, Any] = {}
        self.commands: list[dict[str, Any]] = []
        self.connection: serial.SerialBase | None = None
        self.internal_pending: list[tuple[bytes, dict[str, Any]]] = []

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(50)
        self.poll_timer.timeout.connect(self.poll_connection)

        self.build_ui()
        self.load_protocol(SAMPLE_PROTOCOL)

    def build_ui(self) -> None:
        root = QWidget(self)
        layout = QVBoxLayout(root)

        toolbar = QHBoxLayout()
        self.open_protocol_btn = QPushButton("Open Protocol")
        self.open_protocol_btn.clicked.connect(self.choose_protocol)
        self.connection_mode = QComboBox()
        self.connection_mode.addItems(["Internal virtual", "pyserial URL", "Serial port"])
        self.connection_mode.currentTextChanged.connect(self.connection_mode_changed)
        self.role_combo = QComboBox()
        self.role_combo.addItems(["Host / 上位机", "Device / 下位机"])
        self.port_edit = QLineEdit("loop://")
        self.refresh_ports_btn = QPushButton("Refresh Ports")
        self.refresh_ports_btn.clicked.connect(self.refresh_ports)
        self.baud_spin = QSpinBox()
        self.baud_spin.setRange(300, 4000000)
        self.baud_spin.setValue(115200)
        self.open_btn = QPushButton("Open")
        self.open_btn.clicked.connect(self.toggle_connection)
        self.send_btn = QPushButton("Send Selected")
        self.send_btn.clicked.connect(self.send_selected)
        self.clear_btn = QPushButton("Clear Log")
        self.clear_btn.clicked.connect(self.clear_log)

        for widget in (
            self.open_protocol_btn,
            QLabel("Mode"),
            self.connection_mode,
            QLabel("Role"),
            self.role_combo,
            QLabel("Port/URL"),
            self.port_edit,
            self.refresh_ports_btn,
            QLabel("Baud"),
            self.baud_spin,
            self.open_btn,
            self.send_btn,
            self.clear_btn,
        ):
            toolbar.addWidget(widget)
        toolbar.addStretch(1)
        layout.addLayout(toolbar)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.command_group())
        splitter.addWidget(self.log_group())
        splitter.setSizes([760, 520])
        layout.addWidget(splitter, 1)

        self.setCentralWidget(root)
        self.connection_mode_changed(self.connection_mode.currentText())

    def command_group(self) -> QWidget:
        group = QGroupBox("Commands")
        layout = QVBoxLayout(group)

        self.protocol_label = QLabel("")
        layout.addWidget(self.protocol_label)

        self.command_table = QTableWidget(0, 6)
        self.command_table.setHorizontalHeaderLabels(
            ["Name", "Command Original", "Comment", "Baudrate", "Response Decode", "ID"]
        )
        header = self.command_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.command_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.command_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.command_table.itemDoubleClicked.connect(lambda _item: self.send_selected())
        layout.addWidget(self.command_table, 1)
        return group

    def log_group(self) -> QWidget:
        group = QGroupBox("TX/RX Log")
        layout = QGridLayout(group)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.detail = QTextEdit()
        self.detail.setReadOnly(True)
        self.detail.setMaximumHeight(170)
        layout.addWidget(QLabel("Log"), 0, 0)
        layout.addWidget(self.log, 1, 0)
        layout.addWidget(QLabel("Selected Command Detail"), 2, 0)
        layout.addWidget(self.detail, 3, 0)
        self.command_table_selection_timer = QTimer(self)
        self.command_table_selection_timer.setInterval(200)
        self.command_table_selection_timer.timeout.connect(self.update_selected_detail)
        self.command_table_selection_timer.start()
        return group

    def choose_protocol(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open serial_protocol.v1 JSON",
            str(ROOT),
            "JSON files (*.json);;All files (*)",
        )
        if path:
            self.load_protocol(Path(path))

    def load_protocol(self, path: Path) -> None:
        try:
            self.protocol = json.loads(path.read_text(encoding="utf-8"))
            if self.protocol.get("schema") != "serial_protocol.v1":
                raise ValueError("schema must be serial_protocol.v1")
            self.commands = list(self.protocol.get("commands", []))
        except Exception as exc:  # noqa: BLE001 - user-facing dialog
            QMessageBox.critical(self, "Protocol Error", f"Could not load protocol:\n{exc}")
            return

        metadata = self.protocol.get("metadata", {})
        default_baud = int(metadata.get("default_baudrate", 115200))
        self.baud_spin.setValue(default_baud)
        self.protocol_label.setText(
            f"{metadata.get('name', path.name)} | commands: {len(self.commands)} | default baud: {default_baud}"
        )
        self.populate_table()
        self.append_log("INFO", f"Loaded protocol: {path}")

    def populate_table(self) -> None:
        self.command_table.setRowCount(len(self.commands))
        default_baud = self.protocol.get("metadata", {}).get("default_baudrate", "")

        for row, command in enumerate(self.commands):
            request = command.get("request", {})
            response = command.get("response", {})
            decode_summary = ", ".join(
                (item.get("label") or item.get("name") or item.get("type", "value"))
                for item in response.get("decode", [])
            )
            values = [
                command.get("name", ""),
                request.get("original") or request.get("data", ""),
                command.get("comment", ""),
                str(command.get("baudrate", default_baud)),
                decode_summary,
                command.get("id", ""),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                if command.get("status") == "needs_confirmation":
                    item.setBackground(QColor("#fff3cd"))
                self.command_table.setItem(row, col, item)

        if self.commands:
            self.command_table.selectRow(0)

    def selected_command(self) -> dict[str, Any] | None:
        selected = self.command_table.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        if 0 <= row < len(self.commands):
            return self.commands[row]
        return None

    def update_selected_detail(self) -> None:
        command = self.selected_command()
        if not command:
            self.detail.clear()
            return
        self.detail.setPlainText(json.dumps(command, ensure_ascii=False, indent=2))

    def connection_mode_changed(self, mode: str) -> None:
        if mode == "Internal virtual":
            self.port_edit.setText("")
            self.port_edit.setEnabled(False)
            self.refresh_ports_btn.setEnabled(False)
        elif mode == "pyserial URL":
            self.port_edit.setEnabled(True)
            self.refresh_ports_btn.setEnabled(False)
            if not self.port_edit.text().strip():
                self.port_edit.setText("loop://")
        else:
            self.port_edit.setEnabled(True)
            self.refresh_ports_btn.setEnabled(True)
            self.refresh_ports()

    def refresh_ports(self) -> None:
        ports = [port.device for port in list_ports.comports()]
        if ports:
            self.port_edit.setText(ports[0])
            self.append_log("INFO", "Available ports: " + ", ".join(ports))
        else:
            self.append_log("INFO", "No serial ports detected")

    def serial_settings(self) -> SerialSettings:
        serial_config = self.protocol.get("metadata", {}).get("serial", {})
        return SerialSettings(
            baudrate=int(self.baud_spin.value()),
            bytesize=int(serial_config.get("bytesize", 8)),
            parity=str(serial_config.get("parity", "N")),
            stopbits=float(serial_config.get("stopbits", 1)),
            timeout=0,
        )

    def toggle_connection(self) -> None:
        internal_open = self.connection_mode.currentText() == "Internal virtual" and self.open_btn.text() == "Close"
        if self.connection or internal_open:
            self.close_connection()
            return
        self.open_connection()

    def open_connection(self) -> None:
        mode = self.connection_mode.currentText()
        if mode == "Internal virtual":
            self.open_btn.setText("Close")
            self.append_log("INFO", "Internal virtual connection opened")
            return

        settings = self.serial_settings()
        port = self.port_edit.text().strip()
        if not port:
            QMessageBox.warning(self, "Missing Port", "Please enter a serial port or pyserial URL.")
            return

        try:
            if mode == "pyserial URL":
                self.connection = serial.serial_for_url(
                    port,
                    baudrate=settings.baudrate,
                    bytesize=settings.bytesize,
                    parity=settings.parity,
                    stopbits=settings.stopbits,
                    timeout=settings.timeout,
                )
            else:
                self.connection = serial.Serial(
                    port=port,
                    baudrate=settings.baudrate,
                    bytesize=settings.bytesize,
                    parity=settings.parity,
                    stopbits=settings.stopbits,
                    timeout=settings.timeout,
                )
        except Exception as exc:  # noqa: BLE001 - user-facing dialog
            QMessageBox.critical(self, "Open Failed", str(exc))
            self.connection = None
            return

        self.poll_timer.start()
        self.open_btn.setText("Close")
        self.append_log("INFO", f"Opened {port} at {settings.baudrate} baud")

    def close_connection(self) -> None:
        self.poll_timer.stop()
        if self.connection:
            try:
                self.connection.close()
            finally:
                self.connection = None
        self.internal_pending.clear()
        self.open_btn.setText("Open")
        self.append_log("INFO", "Connection closed")

    def send_selected(self) -> None:
        command = self.selected_command()
        if not command:
            QMessageBox.information(self, "No Command", "Select a command first.")
            return

        request = command.get("request", {})
        try:
            tx_data = payload_to_bytes(request)
        except Exception as exc:  # noqa: BLE001 - user-facing dialog
            QMessageBox.critical(self, "Payload Error", str(exc))
            return

        if self.connection_mode.currentText() == "Internal virtual":
            self.append_tx(command, tx_data)
            reply = command_reply_bytes(command)
            if reply is not None:
                self.internal_pending.append((reply, command))
                QTimer.singleShot(80, self.flush_internal_pending)
            return

        if not self.connection:
            QMessageBox.warning(self, "Not Connected", "Open a connection first.")
            return

        self.connection.write(tx_data)
        self.append_tx(command, tx_data)

    def append_tx(self, command: dict[str, Any], tx_data: bytes) -> None:
        mode = command.get("request", {}).get("mode", "hex")
        self.append_log("TX", f"{command.get('name', command.get('id', 'command'))}: {display_payload(tx_data, mode)}")

    def flush_internal_pending(self) -> None:
        while self.internal_pending:
            data, command = self.internal_pending.pop(0)
            self.append_rx(data, command)

    def poll_connection(self) -> None:
        if not self.connection:
            return
        waiting = getattr(self.connection, "in_waiting", 0)
        if not waiting:
            return
        data = self.connection.read(waiting)
        if not data:
            return

        if self.role_combo.currentText().startswith("Device"):
            command = self.match_command(data)
            self.append_rx(data, command)
            if command:
                reply = command_reply_bytes(command)
                if reply is not None:
                    self.connection.write(reply)
                    self.append_log("TX", f"Auto reply for {command.get('name')}: {bytes_to_hex(reply)}")
            else:
                self.append_log("WARN", "No matching command for incoming request")
        else:
            self.append_rx(data, self.selected_command())

    def match_command(self, data: bytes) -> dict[str, Any] | None:
        for command in self.commands:
            try:
                expected = payload_to_bytes(command.get("request", {}))
            except Exception:
                continue
            if data == expected:
                return command
        return None

    def append_rx(self, data: bytes, command: dict[str, Any] | None) -> None:
        mode = "hex"
        if command:
            mode = command.get("response", {}).get("mode", command.get("request", {}).get("mode", "hex"))
        line = display_payload(data, mode)
        decoded = decode_fields(data, command) if command else ""
        suffix = f" | {decoded}" if decoded else ""
        self.append_log("RX", f"{line}{suffix}")

    def append_log(self, kind: str, message: str) -> None:
        self.log.append(f"[{now()}] {kind:<4} {message}")

    def clear_log(self) -> None:
        self.log.clear()

    def closeEvent(self, event: Any) -> None:  # noqa: N802 - Qt API
        self.close_connection()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    window = SerialConsole()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
