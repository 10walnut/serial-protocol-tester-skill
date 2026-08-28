from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import serial
from serial.tools import list_ports
from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QFormLayout,
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
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from protocol_core import (
    ProtocolError,
    decode_response,
    encode_frame,
    find_matching_command,
    format_hex,
    load_protocol,
)


def resource_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root)
    return Path(__file__).resolve().parent


ROOT = resource_root()
SAMPLE_PROTOCOL = ROOT / "sample_protocol.json"


class SerialConsole(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.protocol: dict[str, Any] | None = None
        self.protocol_path: Path | None = None
        self.serial_port: serial.SerialBase | None = None
        self.connected = False
        self.last_command: dict[str, Any] | None = None
        self.rx_buffer = bytearray()
        self.last_rx_at = 0.0

        self.setWindowTitle("Serial Protocol Tester / 串口协议测试器")
        self.resize(1380, 840)
        self.setMinimumSize(1050, 680)
        self._build_ui()
        self._apply_style()

        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(20)
        self.poll_timer.timeout.connect(self._poll_serial)
        self.poll_timer.start()

        self._refresh_ports()
        if SAMPLE_PROTOCOL.exists():
            self._load_protocol_file(SAMPLE_PROTOCOL)

    def _build_ui(self) -> None:
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(14, 14, 14, 10)
        root.setSpacing(10)

        file_row = QHBoxLayout()
        self.protocol_label = QLabel("No protocol loaded / 未加载协议")
        self.protocol_label.setObjectName("protocolTitle")
        load_button = QPushButton("Load protocol / 加载协议")
        load_button.clicked.connect(self._choose_protocol)
        file_row.addWidget(self.protocol_label, 1)
        file_row.addWidget(load_button)
        root.addLayout(file_row)

        settings = QGroupBox("Connection / 连接")
        settings_layout = QHBoxLayout(settings)

        left_form = QFormLayout()
        self.role_combo = QComboBox()
        self.role_combo.addItem("Host / 上位机", "host")
        self.role_combo.addItem("Device / 下位机", "device")
        self.role_combo.currentIndexChanged.connect(self._sync_role_ui)
        left_form.addRow("Role / 角色", self.role_combo)

        self.transport_combo = QComboBox()
        self.transport_combo.addItem("Internal virtual link / 内部虚拟链路", "internal")
        self.transport_combo.addItem("COM port or serial URL / 串口或 URL", "serial")
        self.transport_combo.currentIndexChanged.connect(self._sync_transport_ui)
        left_form.addRow("Transport / 通道", self.transport_combo)
        settings_layout.addLayout(left_form, 2)

        middle_form = QFormLayout()
        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.port_combo.setPlaceholderText("COM3 or loop://")
        refresh_button = QPushButton("Refresh / 刷新")
        refresh_button.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(refresh_button)
        middle_form.addRow("Endpoint / 端口", port_row)

        self.baudrate_spin = QSpinBox()
        self.baudrate_spin.setRange(50, 4_000_000)
        self.baudrate_spin.setValue(9600)
        middle_form.addRow("Baud rate / 波特率", self.baudrate_spin)
        settings_layout.addLayout(middle_form, 3)

        serial_form = QFormLayout()
        self.bytesize_combo = QComboBox()
        self.bytesize_combo.addItems(["5", "6", "7", "8"])
        self.bytesize_combo.setCurrentText("8")
        serial_form.addRow("Data bits / 数据位", self.bytesize_combo)
        self.parity_combo = QComboBox()
        for text, value in [("None / 无", "N"), ("Even / 偶", "E"), ("Odd / 奇", "O"), ("Mark", "M"), ("Space", "S")]:
            self.parity_combo.addItem(text, value)
        serial_form.addRow("Parity / 校验位", self.parity_combo)
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "1.5", "2"])
        serial_form.addRow("Stop bits / 停止位", self.stopbits_combo)
        settings_layout.addLayout(serial_form, 2)

        action_column = QVBoxLayout()
        self.connect_button = QPushButton("Open / 打开")
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.clicked.connect(self._toggle_connection)
        self.connection_label = QLabel("Closed / 已关闭")
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_column.addWidget(self.connect_button)
        action_column.addWidget(self.connection_label)
        action_column.addStretch(1)
        settings_layout.addLayout(action_column, 1)
        root.addWidget(settings)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        command_group = QGroupBox("Commands / 命令")
        command_layout = QVBoxLayout(command_group)
        self.command_table = QTableWidget(0, 6)
        self.command_table.setHorizontalHeaderLabels(
            ["Name / 名称", "Request / 命令原文", "Annotation / 注释", "Baud / 波特率", "Response / 返回原文", "ID"]
        )
        self.command_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.command_table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.command_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.command_table.setAlternatingRowColors(True)
        self.command_table.verticalHeader().setVisible(False)
        header = self.command_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.command_table.itemSelectionChanged.connect(self._show_selected_command)
        self.command_table.cellDoubleClicked.connect(lambda _row, _column: self._run_selected_command())
        command_layout.addWidget(self.command_table, 1)

        detail_row = QHBoxLayout()
        self.command_detail = QLineEdit()
        self.command_detail.setReadOnly(True)
        self.command_detail.setPlaceholderText("Select a command / 请选择命令")
        self.command_action_button = QPushButton("Send request / 发送请求")
        self.command_action_button.setObjectName("primaryButton")
        self.command_action_button.clicked.connect(self._run_selected_command)
        detail_row.addWidget(self.command_detail, 1)
        detail_row.addWidget(self.command_action_button)
        command_layout.addLayout(detail_row)
        splitter.addWidget(command_group)

        output_group = QGroupBox("Traffic and decoded response / 通讯记录与返回解析")
        output_layout = QVBoxLayout(output_group)
        self.log_table = QTableWidget(0, 5)
        self.log_table.setHorizontalHeaderLabels(
            ["Time / 时间", "Dir / 方向", "Command / 命令", "Raw HEX / 原始数据", "Text / 文本"]
        )
        self.log_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.log_table.setAlternatingRowColors(True)
        self.log_table.verticalHeader().setVisible(False)
        log_header = self.log_table.horizontalHeader()
        log_header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        log_header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        log_header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        log_header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        log_header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        output_layout.addWidget(self.log_table, 3)

        decoded_header = QHBoxLayout()
        decoded_header.addWidget(QLabel("Decoded fields / 返回数据转换"))
        decoded_header.addStretch(1)
        clear_button = QPushButton("Clear / 清空")
        clear_button.clicked.connect(self._clear_output)
        decoded_header.addWidget(clear_button)
        output_layout.addLayout(decoded_header)

        self.decoded_table = QTableWidget(0, 4)
        self.decoded_table.setHorizontalHeaderLabels(
            ["Field / 字段", "Raw / 原始", "Value / 转换值", "Key / 键"]
        )
        self.decoded_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.decoded_table.verticalHeader().setVisible(False)
        decoded_table_header = self.decoded_table.horizontalHeader()
        decoded_table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        decoded_table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        decoded_table_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        decoded_table_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        output_layout.addWidget(self.decoded_table, 2)
        splitter.addWidget(output_group)
        splitter.setSizes([760, 620])
        root.addWidget(splitter, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self.statusBar().showMessage("Ready / 就绪")
        self._sync_transport_ui()
        self._sync_role_ui()

    def _apply_style(self) -> None:
        mono = QFont("Consolas")
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self.command_table.setFont(mono)
        self.log_table.setFont(mono)
        self.decoded_table.setFont(mono)
        self.setStyleSheet(
            """
            QMainWindow, QWidget { background: #f5f7f8; color: #1d262d; font-size: 13px; }
            QGroupBox { background: #ffffff; border: 1px solid #cfd7dc; border-radius: 6px;
                        margin-top: 12px; padding-top: 10px; font-weight: 600; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLabel#protocolTitle { font-size: 18px; font-weight: 700; color: #172126; }
            QPushButton { min-height: 30px; padding: 0 12px; background: #ffffff;
                          border: 1px solid #aebbc2; border-radius: 5px; }
            QPushButton:hover { background: #eef4f4; border-color: #608087; }
            QPushButton:disabled { color: #8b969c; background: #edf0f1; }
            QPushButton#primaryButton { color: #ffffff; background: #176b70; border-color: #176b70; font-weight: 600; }
            QPushButton#primaryButton:hover { background: #10585d; }
            QComboBox, QSpinBox, QLineEdit { min-height: 28px; background: #ffffff;
                                            border: 1px solid #b9c4ca; border-radius: 4px; padding: 0 6px; }
            QTableWidget { background: #ffffff; alternate-background-color: #f2f6f6;
                           border: 1px solid #cfd7dc; gridline-color: #dce3e6; }
            QHeaderView::section { background: #e7ecee; color: #26343a; padding: 7px;
                                   border: 0; border-right: 1px solid #ccd5d9; font-weight: 600; }
            QTableWidget::item:selected { background: #cfe4e4; color: #101719; }
            QStatusBar { background: #e7ecee; }
            """
        )

    def _choose_protocol(self) -> None:
        start_dir = str(self.protocol_path.parent if self.protocol_path else ROOT)
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load protocol / 加载协议",
            start_dir,
            "Serial protocol (*.json);;All files (*)",
        )
        if path:
            self._load_protocol_file(Path(path))

    def _load_protocol_file(self, path: Path) -> None:
        try:
            protocol = load_protocol(path)
        except ProtocolError as exc:
            QMessageBox.critical(self, "Protocol error / 协议错误", str(exc))
            return
        self.protocol = protocol
        self.protocol_path = path
        self.protocol_label.setText(f"{protocol['name']}  ·  {path.name}")
        defaults = protocol["serial"]["defaults"]
        self.baudrate_spin.setValue(defaults["baudrate"])
        self.bytesize_combo.setCurrentText(str(defaults.get("bytesize", 8)))
        parity_index = self.parity_combo.findData(defaults.get("parity", "N"))
        self.parity_combo.setCurrentIndex(max(0, parity_index))
        self.stopbits_combo.setCurrentText(str(defaults.get("stopbits", 1)))
        self._populate_commands()
        self.statusBar().showMessage(f"Loaded {len(protocol['commands'])} commands / 已加载 {len(protocol['commands'])} 条命令")

    def _populate_commands(self) -> None:
        commands = self.protocol["commands"] if self.protocol else []
        default_baud = self._serial_defaults().get("baudrate", 9600)
        self.command_table.setRowCount(len(commands))
        for row, command in enumerate(commands):
            request = format_hex(encode_frame(command["request"]))
            response = format_hex(encode_frame(command["response"])) if command.get("response") else "—"
            values = [
                command["name"],
                request,
                command.get("description", ""),
                str(command.get("baudrate", default_baud)),
                response,
                command["id"],
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                self.command_table.setItem(row, column, item)
        if commands:
            self.command_table.selectRow(0)

    def _selected_command(self) -> dict[str, Any] | None:
        if not self.protocol:
            return None
        row = self.command_table.currentRow()
        if row < 0 or row >= len(self.protocol["commands"]):
            return None
        return self.protocol["commands"][row]

    def _show_selected_command(self) -> None:
        command = self._selected_command()
        if not command:
            self.command_detail.clear()
            return
        request = format_hex(encode_frame(command["request"]))
        self.command_detail.setText(f"{command['id']}  |  {request}  |  {command.get('description', '')}")

    def _sync_role_ui(self) -> None:
        role = self.role_combo.currentData()
        if role == "host":
            self.command_action_button.setText("Send request / 发送请求")
        elif self.transport_combo.currentData() == "internal":
            self.command_action_button.setText("Simulate request / 模拟收到请求")
        else:
            self.command_action_button.setText("Send response / 手动发送应答")

    def _sync_transport_ui(self) -> None:
        serial_enabled = self.transport_combo.currentData() == "serial"
        self.port_combo.setEnabled(serial_enabled and not self.connected)
        self.bytesize_combo.setEnabled(serial_enabled and not self.connected)
        self.parity_combo.setEnabled(serial_enabled and not self.connected)
        self.stopbits_combo.setEnabled(serial_enabled and not self.connected)
        self._sync_role_ui()

    def _refresh_ports(self) -> None:
        current = self.port_combo.currentText() if hasattr(self, "port_combo") else ""
        if not hasattr(self, "port_combo"):
            return
        ports = [port.device for port in list_ports.comports()]
        self.port_combo.clear()
        self.port_combo.addItems(ports)
        if current:
            index = self.port_combo.findText(current)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)
            else:
                self.port_combo.setEditText(current)

    def _serial_defaults(self) -> dict[str, Any]:
        if not self.protocol:
            return {"baudrate": 9600, "bytesize": 8, "parity": "N", "stopbits": 1, "timeout_ms": 200}
        return self.protocol["serial"]["defaults"]

    def _toggle_connection(self) -> None:
        if self.connected:
            self._close_connection()
        else:
            self._open_connection()

    def _open_connection(self) -> None:
        if not self.protocol:
            QMessageBox.warning(self, "No protocol / 未加载协议", "Load a protocol JSON first. / 请先加载协议 JSON。")
            return
        transport = self.transport_combo.currentData()
        try:
            if transport == "serial":
                endpoint = self.port_combo.currentText().strip()
                if not endpoint:
                    raise ValueError("Select a COM port or enter a serial URL such as loop://")
                self.serial_port = serial.serial_for_url(
                    endpoint,
                    baudrate=self.baudrate_spin.value(),
                    bytesize=int(self.bytesize_combo.currentText()),
                    parity=self.parity_combo.currentData(),
                    stopbits=float(self.stopbits_combo.currentText()),
                    timeout=0,
                    write_timeout=1,
                )
            self.connected = True
            self.connect_button.setText("Close / 关闭")
            self.connection_label.setText("Open / 已打开")
            self.connection_label.setStyleSheet("color: #176b70; font-weight: 700;")
            self.transport_combo.setEnabled(False)
            self.role_combo.setEnabled(False)
            self._sync_transport_ui()
            endpoint_name = "internal virtual link" if transport == "internal" else self.port_combo.currentText()
            self.statusBar().showMessage(f"Connected: {endpoint_name} / 已连接")
        except (serial.SerialException, ValueError, OSError) as exc:
            QMessageBox.critical(self, "Connection failed / 连接失败", str(exc))
            self.statusBar().showMessage(f"Connection failed: {exc}")

    def _close_connection(self) -> None:
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except serial.SerialException:
                pass
        self.serial_port = None
        self.connected = False
        self.rx_buffer.clear()
        self.connect_button.setText("Open / 打开")
        self.connection_label.setText("Closed / 已关闭")
        self.connection_label.setStyleSheet("")
        self.transport_combo.setEnabled(True)
        self.role_combo.setEnabled(True)
        self._sync_transport_ui()
        self.statusBar().showMessage("Closed / 已关闭")

    def _set_command_baudrate(self, command: dict[str, Any]) -> None:
        baudrate = command.get("baudrate", self._serial_defaults()["baudrate"])
        self.baudrate_spin.setValue(baudrate)
        if self.serial_port is not None:
            self.serial_port.baudrate = baudrate

    def _run_selected_command(self) -> None:
        command = self._selected_command()
        if not command:
            QMessageBox.information(self, "No command / 未选择命令", "Select a command first. / 请先选择命令。")
            return
        if not self.connected:
            QMessageBox.information(self, "Not connected / 未连接", "Open the connection first. / 请先打开连接。")
            return
        try:
            self._set_command_baudrate(command)
            role = self.role_combo.currentData()
            internal = self.transport_combo.currentData() == "internal"
            if role == "host":
                request = encode_frame(command["request"])
                self.last_command = command
                self._transmit(request, command, "TX")
                if internal and command.get("response"):
                    QTimer.singleShot(80, lambda: self._receive_internal_response(command))
            elif internal:
                request = encode_frame(command["request"])
                self._handle_received_frame(request)
            elif command.get("response"):
                self._transmit(encode_frame(command["response"]), command, "TX")
            else:
                QMessageBox.information(self, "No response / 无应答", "This command has no configured response.")
        except (ProtocolError, serial.SerialException, OSError, ValueError) as exc:
            self._report_runtime_error(exc)

    def _transmit(self, data: bytes, command: dict[str, Any] | None, direction: str) -> None:
        if self.transport_combo.currentData() == "serial":
            if self.serial_port is None:
                raise serial.SerialException("serial port is not open")
            self.serial_port.write(data)
            self.serial_port.flush()
        self._append_log(direction, data, command)

    def _receive_internal_response(self, command: dict[str, Any]) -> None:
        if not self.connected or self.transport_combo.currentData() != "internal":
            return
        response = command.get("response")
        if response:
            self._handle_received_frame(encode_frame(response), command)

    def _poll_serial(self) -> None:
        if not self.connected or self.serial_port is None:
            return
        try:
            waiting = self.serial_port.in_waiting
            if waiting:
                self.rx_buffer.extend(self.serial_port.read(waiting))
                self.last_rx_at = time.monotonic()
            elif self.rx_buffer and time.monotonic() - self.last_rx_at >= 0.04:
                frame = bytes(self.rx_buffer)
                self.rx_buffer.clear()
                self._handle_received_frame(frame)
        except (serial.SerialException, OSError) as exc:
            self._report_runtime_error(exc)
            self._close_connection()

    def _handle_received_frame(self, data: bytes, known_command: dict[str, Any] | None = None) -> None:
        command = known_command
        if command is None and self.protocol:
            if self.role_combo.currentData() == "device":
                try:
                    command = find_matching_command(data, self.protocol["commands"])
                except ProtocolError as exc:
                    self._report_runtime_error(exc)
            else:
                command = self.last_command
        self._append_log("RX", data, command)
        if command and self.role_combo.currentData() == "host":
            self._display_decoded(data, command.get("response"))
        if command and self.role_combo.currentData() == "device" and command.get("auto_reply") and command.get("response"):
            QTimer.singleShot(50, lambda: self._send_automatic_response(command))

    def _send_automatic_response(self, command: dict[str, Any]) -> None:
        if not self.connected:
            return
        try:
            response = encode_frame(command["response"])
            self._transmit(response, command, "TX")
            self._display_decoded(response, command.get("response"))
        except (ProtocolError, serial.SerialException, OSError) as exc:
            self._report_runtime_error(exc)

    def _append_log(self, direction: str, data: bytes, command: dict[str, Any] | None) -> None:
        row = self.log_table.rowCount()
        self.log_table.insertRow(row)
        now = time.strftime("%H:%M:%S") + f".{int(time.time() * 1000) % 1000:03d}"
        try:
            text_preview = data.decode("utf-8").replace("\r", "\\r").replace("\n", "\\n")
            if not text_preview.isprintable():
                text_preview = ""
        except UnicodeDecodeError:
            text_preview = ""
        command_name = command.get("name", "Unmatched / 未匹配") if command else "Unmatched / 未匹配"
        values = [now, direction, command_name, format_hex(data), text_preview]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            if column == 1:
                item.setForeground(Qt.GlobalColor.darkGreen if direction == "RX" else Qt.GlobalColor.darkBlue)
            self.log_table.setItem(row, column, item)
        self.log_table.scrollToBottom()
        self.statusBar().showMessage(f"{direction} {len(data)} bytes · {command_name}")

    def _display_decoded(self, data: bytes, response: dict[str, Any] | None) -> None:
        fields = decode_response(data, response)
        self.decoded_table.setRowCount(len(fields))
        for row, field in enumerate(fields):
            values = [field["label"], field["raw"], field["display"], field["name"]]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setToolTip(str(value))
                self.decoded_table.setItem(row, column, item)

    def _clear_output(self) -> None:
        self.log_table.setRowCount(0)
        self.decoded_table.setRowCount(0)
        self.statusBar().showMessage("Output cleared / 已清空")

    def _report_runtime_error(self, error: Exception) -> None:
        QMessageBox.critical(self, "Serial error / 串口错误", str(error))
        self.statusBar().showMessage(f"Error: {error}")

    def closeEvent(self, event: Any) -> None:
        self._close_connection()
        event.accept()


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Serial Protocol Tester")
    app.setWindowIcon(QIcon())
    window = SerialConsole()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
