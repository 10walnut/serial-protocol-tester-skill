from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any

import serial
from serial.tools import list_ports
from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
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
from virtual_ports import (
    COM0COM_DOWNLOAD_URL,
    VirtualPortError,
    find_setupc,
    launch_elevated_install,
    list_virtual_pairs,
)


def resource_root() -> Path:
    bundled_root = getattr(sys, "_MEIPASS", None)
    if bundled_root:
        return Path(bundled_root)
    return Path(__file__).resolve().parent


ROOT = resource_root()
SAMPLE_PROTOCOL = ROOT / "sample_protocol.json"


UI_TEXT = {
    "zh": {
        "title": "串口协议测试器",
        "language_button": "EN",
        "no_protocol": "未加载协议",
        "load_protocol": "加载协议",
        "connection": "连接设置",
        "role": "角色",
        "host": "上位机",
        "device": "下位机",
        "transport": "通信通道",
        "internal_transport": "内部虚拟链路",
        "serial_transport": "串口或 URL",
        "endpoint": "端口",
        "refresh": "刷新",
        "virtual_ports": "虚拟串口",
        "baudrate": "波特率",
        "data_bits": "数据位",
        "parity": "校验位",
        "parity_none": "无",
        "parity_even": "偶校验",
        "parity_odd": "奇校验",
        "parity_mark": "标记",
        "parity_space": "空格",
        "stop_bits": "停止位",
        "open": "打开",
        "close": "关闭",
        "opened": "已打开",
        "closed": "已关闭",
        "commands": "命令",
        "command_headers": ["名称", "命令原文", "注释", "波特率", "返回原文", "ID"],
        "select_command": "请选择命令",
        "send_request": "发送请求",
        "simulate_request": "模拟收到请求",
        "send_response": "手动发送应答",
        "traffic": "通讯记录与返回解析",
        "log_headers": ["时间", "方向", "命令", "原始 HEX", "文本"],
        "decoded_fields": "返回数据转换",
        "clear": "清空",
        "decoded_headers": ["字段", "原始数据", "转换值", "键"],
        "ready": "就绪",
        "load_dialog_title": "加载协议",
        "file_filter": "串口协议 (*.json);;所有文件 (*)",
        "protocol_error": "协议错误",
        "loaded_commands": "已加载 {count} 条命令",
        "no_protocol_title": "未加载协议",
        "no_protocol_message": "请先加载协议 JSON。",
        "endpoint_required": "请选择 COM 端口，或输入 loop:// 等串口 URL",
        "internal_name": "内部虚拟链路",
        "connected": "已连接：{endpoint}",
        "connection_failed": "连接失败",
        "connection_failed_status": "连接失败：{error}",
        "closed_status": "连接已关闭",
        "no_command_title": "未选择命令",
        "no_command_message": "请先选择一条命令。",
        "not_connected_title": "未连接",
        "not_connected_message": "请先打开连接。",
        "no_response_title": "无应答",
        "no_response_message": "该命令没有配置应答帧。",
        "unmatched": "未匹配",
        "traffic_status": "{direction} {count} 字节 · {command}",
        "output_cleared": "已清空输出",
        "serial_error": "串口错误",
        "error_status": "错误：{error}",
        "vp_title": "创建虚拟串口对",
        "vp_intro": "本功能调用已安装的 com0com 驱动创建两个互联 COM 端口。创建时 Windows 会请求管理员权限。",
        "vp_driver": "setupc.exe 路径",
        "vp_browse": "选择",
        "vp_port_a": "本软件端口",
        "vp_port_b": "外部软件端口",
        "vp_create": "创建端口对",
        "vp_refresh": "刷新状态",
        "vp_close": "关闭",
        "vp_not_found": "未检测到 com0com。请先从官方项目安装驱动，或手动选择 setupc.exe。",
        "vp_found": "已检测到 com0com：{path}",
        "vp_download": "打开 com0com 官方下载页面",
        "vp_existing": "com0com 当前端口",
        "vp_no_output": "尚未读取端口状态。",
        "vp_select_title": "选择 com0com setupc.exe",
        "vp_executable_filter": "程序 (setupc.exe);;所有文件 (*)",
        "vp_driver_missing_title": "缺少虚拟串口驱动",
        "vp_driver_missing_message": "未找到 setupc.exe。请先安装 com0com 或选择正确路径。",
        "vp_invalid_title": "端口设置无效",
        "vp_same_port": "两个端口号不能相同。",
        "vp_conflict_title": "端口号已占用",
        "vp_conflict_message": "以下端口已存在：{ports}\n请选择其他端口号。",
        "vp_uac_title": "确认创建虚拟串口",
        "vp_uac_message": "将创建 {port_a} ↔ {port_b}。Windows 随后会显示管理员权限确认窗口。是否继续？",
        "vp_started_title": "已启动创建",
        "vp_started_message": "已请求创建 {port_a} ↔ {port_b}。请完成 UAC 和驱动确认，然后点击“刷新状态”。",
        "vp_error_title": "虚拟串口错误",
    },
    "en": {
        "title": "Serial Protocol Tester",
        "language_button": "中文",
        "no_protocol": "No protocol loaded",
        "load_protocol": "Load protocol",
        "connection": "Connection",
        "role": "Role",
        "host": "Host",
        "device": "Device",
        "transport": "Transport",
        "internal_transport": "Internal virtual link",
        "serial_transport": "COM port or serial URL",
        "endpoint": "Endpoint",
        "refresh": "Refresh",
        "virtual_ports": "Virtual ports",
        "baudrate": "Baud rate",
        "data_bits": "Data bits",
        "parity": "Parity",
        "parity_none": "None",
        "parity_even": "Even",
        "parity_odd": "Odd",
        "parity_mark": "Mark",
        "parity_space": "Space",
        "stop_bits": "Stop bits",
        "open": "Open",
        "close": "Close",
        "opened": "Open",
        "closed": "Closed",
        "commands": "Commands",
        "command_headers": ["Name", "Request", "Annotation", "Baud", "Response", "ID"],
        "select_command": "Select a command",
        "send_request": "Send request",
        "simulate_request": "Simulate request",
        "send_response": "Send response",
        "traffic": "Traffic and decoded response",
        "log_headers": ["Time", "Direction", "Command", "Raw HEX", "Text"],
        "decoded_fields": "Decoded fields",
        "clear": "Clear",
        "decoded_headers": ["Field", "Raw", "Value", "Key"],
        "ready": "Ready",
        "load_dialog_title": "Load protocol",
        "file_filter": "Serial protocol (*.json);;All files (*)",
        "protocol_error": "Protocol error",
        "loaded_commands": "Loaded {count} commands",
        "no_protocol_title": "No protocol",
        "no_protocol_message": "Load a protocol JSON first.",
        "endpoint_required": "Select a COM port or enter a serial URL such as loop://",
        "internal_name": "internal virtual link",
        "connected": "Connected: {endpoint}",
        "connection_failed": "Connection failed",
        "connection_failed_status": "Connection failed: {error}",
        "closed_status": "Connection closed",
        "no_command_title": "No command",
        "no_command_message": "Select a command first.",
        "not_connected_title": "Not connected",
        "not_connected_message": "Open the connection first.",
        "no_response_title": "No response",
        "no_response_message": "This command has no configured response frame.",
        "unmatched": "Unmatched",
        "traffic_status": "{direction} {count} bytes · {command}",
        "output_cleared": "Output cleared",
        "serial_error": "Serial error",
        "error_status": "Error: {error}",
        "vp_title": "Create virtual COM pair",
        "vp_intro": "This feature calls an installed com0com driver to create two linked COM ports. Windows administrator approval is required.",
        "vp_driver": "setupc.exe path",
        "vp_browse": "Browse",
        "vp_port_a": "This application",
        "vp_port_b": "External application",
        "vp_create": "Create port pair",
        "vp_refresh": "Refresh status",
        "vp_close": "Close",
        "vp_not_found": "com0com was not detected. Install it from the official project first, or select setupc.exe manually.",
        "vp_found": "com0com detected: {path}",
        "vp_download": "Open the official com0com download page",
        "vp_existing": "Current com0com ports",
        "vp_no_output": "Port status has not been read yet.",
        "vp_select_title": "Select com0com setupc.exe",
        "vp_executable_filter": "Program (setupc.exe);;All files (*)",
        "vp_driver_missing_title": "Virtual port driver missing",
        "vp_driver_missing_message": "setupc.exe was not found. Install com0com or select the correct path.",
        "vp_invalid_title": "Invalid port settings",
        "vp_same_port": "The two port numbers must be different.",
        "vp_conflict_title": "COM number already in use",
        "vp_conflict_message": "These ports already exist: {ports}\nChoose different port numbers.",
        "vp_uac_title": "Confirm virtual port creation",
        "vp_uac_message": "Create {port_a} ↔ {port_b}? Windows will request administrator approval.",
        "vp_started_title": "Creation started",
        "vp_started_message": "Creation of {port_a} ↔ {port_b} was requested. Complete the UAC and driver prompts, then click Refresh status.",
        "vp_error_title": "Virtual port error",
    },
}


def ui_text(language: str, key: str, **values: Any) -> Any:
    text = UI_TEXT[language][key]
    return text.format(**values) if isinstance(text, str) and values else text


class VirtualPortDialog(QDialog):
    def __init__(self, language: str, refresh_callback: Any, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.language = language
        self.refresh_callback = refresh_callback
        self.setWindowTitle(ui_text(language, "vp_title"))
        self.resize(700, 500)
        self.setMinimumSize(620, 430)
        self._build_ui()
        self._refresh_driver_state()

    def _t(self, key: str, **values: Any) -> Any:
        return ui_text(self.language, key, **values)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        intro = QLabel(self._t("vp_intro"))
        intro.setWordWrap(True)
        layout.addWidget(intro)

        download_link = QLabel(f'<a href="{COM0COM_DOWNLOAD_URL}">{self._t("vp_download")}</a>')
        download_link.setOpenExternalLinks(False)
        download_link.linkActivated.connect(lambda url: QDesktopServices.openUrl(QUrl(url)))
        layout.addWidget(download_link)

        grid = QGridLayout()
        self.setupc_edit = QLineEdit()
        self.setupc_edit.setPlaceholderText(r"C:\Program Files\com0com\setupc.exe")
        browse_button = QPushButton(self._t("vp_browse"))
        browse_button.clicked.connect(self._browse_setupc)
        grid.addWidget(QLabel(self._t("vp_driver")), 0, 0)
        grid.addWidget(self.setupc_edit, 0, 1, 1, 3)
        grid.addWidget(browse_button, 0, 4)

        self.port_a_spin = QSpinBox()
        self.port_a_spin.setRange(1, 256)
        self.port_a_spin.setValue(10)
        self.port_a_spin.setPrefix("COM")
        self.port_b_spin = QSpinBox()
        self.port_b_spin.setRange(1, 256)
        self.port_b_spin.setValue(11)
        self.port_b_spin.setPrefix("COM")
        grid.addWidget(QLabel(self._t("vp_port_a")), 1, 0)
        grid.addWidget(self.port_a_spin, 1, 1)
        grid.addWidget(QLabel("↔"), 1, 2, alignment=Qt.AlignmentFlag.AlignCenter)
        grid.addWidget(QLabel(self._t("vp_port_b")), 1, 3)
        grid.addWidget(self.port_b_spin, 1, 4)
        layout.addLayout(grid)

        self.driver_status = QLabel()
        self.driver_status.setWordWrap(True)
        layout.addWidget(self.driver_status)
        layout.addWidget(QLabel(self._t("vp_existing")))
        self.pair_output = QPlainTextEdit()
        self.pair_output.setReadOnly(True)
        self.pair_output.setPlaceholderText(self._t("vp_no_output"))
        layout.addWidget(self.pair_output, 1)

        buttons = QHBoxLayout()
        self.create_button = QPushButton(self._t("vp_create"))
        self.create_button.setObjectName("primaryButton")
        self.create_button.clicked.connect(self._create_pair)
        refresh_button = QPushButton(self._t("vp_refresh"))
        refresh_button.clicked.connect(self._refresh_driver_state)
        close_button = QPushButton(self._t("vp_close"))
        close_button.clicked.connect(self.accept)
        buttons.addWidget(self.create_button)
        buttons.addWidget(refresh_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)
        layout.addLayout(buttons)

    def _selected_setupc(self) -> Path | None:
        value = self.setupc_edit.text().strip()
        return find_setupc(value or None)

    def _browse_setupc(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            self._t("vp_select_title"),
            self.setupc_edit.text().strip(),
            self._t("vp_executable_filter"),
        )
        if path:
            self.setupc_edit.setText(path)
            self._refresh_driver_state()

    def _refresh_driver_state(self) -> None:
        setupc = self._selected_setupc()
        self.create_button.setEnabled(setupc is not None)
        if setupc is None:
            self.driver_status.setText(self._t("vp_not_found"))
            self.driver_status.setStyleSheet("color: #9a4f00;")
            return
        self.setupc_edit.setText(str(setupc))
        self.driver_status.setText(self._t("vp_found", path=setupc))
        self.driver_status.setStyleSheet("color: #176b70; font-weight: 600;")
        try:
            self.pair_output.setPlainText(list_virtual_pairs(setupc))
        except VirtualPortError as exc:
            self.pair_output.setPlainText(str(exc))
        self.refresh_callback()

    def _create_pair(self) -> None:
        setupc = self._selected_setupc()
        if setupc is None:
            QMessageBox.warning(self, self._t("vp_driver_missing_title"), self._t("vp_driver_missing_message"))
            return
        port_a = f"COM{self.port_a_spin.value()}"
        port_b = f"COM{self.port_b_spin.value()}"
        if port_a == port_b:
            QMessageBox.warning(self, self._t("vp_invalid_title"), self._t("vp_same_port"))
            return
        existing = {port.device.upper() for port in list_ports.comports()}
        conflicts = [port for port in (port_a, port_b) if port in existing]
        if conflicts:
            QMessageBox.warning(
                self,
                self._t("vp_conflict_title"),
                self._t("vp_conflict_message", ports=", ".join(conflicts)),
            )
            return
        answer = QMessageBox.question(
            self,
            self._t("vp_uac_title"),
            self._t("vp_uac_message", port_a=port_a, port_b=port_b),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            launch_elevated_install(setupc, port_a, port_b)
        except VirtualPortError as exc:
            QMessageBox.critical(self, self._t("vp_error_title"), str(exc))
            return
        QMessageBox.information(
            self,
            self._t("vp_started_title"),
            self._t("vp_started_message", port_a=port_a, port_b=port_b),
        )
        QTimer.singleShot(3000, self._refresh_driver_state)


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
        self.language = "zh"

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
        self.protocol_label = QLabel()
        self.protocol_label.setObjectName("protocolTitle")
        self.load_button = QPushButton()
        self.load_button.clicked.connect(self._choose_protocol)
        self.language_button = QPushButton()
        self.language_button.setFixedWidth(58)
        self.language_button.clicked.connect(self._toggle_language)
        file_row.addWidget(self.protocol_label, 1)
        file_row.addWidget(self.language_button)
        file_row.addWidget(self.load_button)
        root.addLayout(file_row)

        self.settings_group = QGroupBox()
        settings_layout = QHBoxLayout(self.settings_group)

        left_form = QFormLayout()
        self.role_label = QLabel()
        self.role_combo = QComboBox()
        self.role_combo.addItem("", "host")
        self.role_combo.addItem("", "device")
        self.role_combo.currentIndexChanged.connect(self._sync_role_ui)
        left_form.addRow(self.role_label, self.role_combo)

        self.transport_label = QLabel()
        self.transport_combo = QComboBox()
        self.transport_combo.addItem("", "internal")
        self.transport_combo.addItem("", "serial")
        self.transport_combo.currentIndexChanged.connect(self._sync_transport_ui)
        left_form.addRow(self.transport_label, self.transport_combo)
        settings_layout.addLayout(left_form, 2)

        middle_form = QFormLayout()
        self.endpoint_label = QLabel()
        port_row = QHBoxLayout()
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.port_combo.setPlaceholderText("COM3 or loop://")
        self.refresh_button = QPushButton()
        self.refresh_button.clicked.connect(self._refresh_ports)
        self.virtual_ports_button = QPushButton()
        self.virtual_ports_button.clicked.connect(self._show_virtual_ports)
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(self.refresh_button)
        port_row.addWidget(self.virtual_ports_button)
        middle_form.addRow(self.endpoint_label, port_row)

        self.baudrate_label = QLabel()
        self.baudrate_spin = QSpinBox()
        self.baudrate_spin.setRange(50, 4_000_000)
        self.baudrate_spin.setValue(9600)
        middle_form.addRow(self.baudrate_label, self.baudrate_spin)
        settings_layout.addLayout(middle_form, 3)

        serial_form = QFormLayout()
        self.bytesize_label = QLabel()
        self.bytesize_combo = QComboBox()
        self.bytesize_combo.addItems(["5", "6", "7", "8"])
        self.bytesize_combo.setCurrentText("8")
        serial_form.addRow(self.bytesize_label, self.bytesize_combo)
        self.parity_label = QLabel()
        self.parity_combo = QComboBox()
        for value in ("N", "E", "O", "M", "S"):
            self.parity_combo.addItem("", value)
        serial_form.addRow(self.parity_label, self.parity_combo)
        self.stopbits_label = QLabel()
        self.stopbits_combo = QComboBox()
        self.stopbits_combo.addItems(["1", "1.5", "2"])
        serial_form.addRow(self.stopbits_label, self.stopbits_combo)
        settings_layout.addLayout(serial_form, 2)

        action_column = QVBoxLayout()
        self.connect_button = QPushButton()
        self.connect_button.setObjectName("primaryButton")
        self.connect_button.clicked.connect(self._toggle_connection)
        self.connection_label = QLabel()
        self.connection_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        action_column.addWidget(self.connect_button)
        action_column.addWidget(self.connection_label)
        action_column.addStretch(1)
        settings_layout.addLayout(action_column, 1)
        root.addWidget(self.settings_group)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        self.command_group = QGroupBox()
        command_layout = QVBoxLayout(self.command_group)
        self.command_table = QTableWidget(0, 6)
        self.command_table.setHorizontalHeaderLabels(["", "", "", "", "", ""])
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
        self.command_action_button = QPushButton()
        self.command_action_button.setObjectName("primaryButton")
        self.command_action_button.clicked.connect(self._run_selected_command)
        detail_row.addWidget(self.command_detail, 1)
        detail_row.addWidget(self.command_action_button)
        command_layout.addLayout(detail_row)
        splitter.addWidget(self.command_group)

        self.output_group = QGroupBox()
        output_layout = QVBoxLayout(self.output_group)
        self.log_table = QTableWidget(0, 5)
        self.log_table.setHorizontalHeaderLabels(["", "", "", "", ""])
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
        self.decoded_fields_label = QLabel()
        decoded_header.addWidget(self.decoded_fields_label)
        decoded_header.addStretch(1)
        self.clear_button = QPushButton()
        self.clear_button.clicked.connect(self._clear_output)
        decoded_header.addWidget(self.clear_button)
        output_layout.addLayout(decoded_header)

        self.decoded_table = QTableWidget(0, 4)
        self.decoded_table.setHorizontalHeaderLabels(["", "", "", ""])
        self.decoded_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.decoded_table.verticalHeader().setVisible(False)
        decoded_table_header = self.decoded_table.horizontalHeader()
        decoded_table_header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        decoded_table_header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        decoded_table_header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        decoded_table_header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        output_layout.addWidget(self.decoded_table, 2)
        splitter.addWidget(self.output_group)
        splitter.setSizes([760, 620])
        root.addWidget(splitter, 1)

        self.setCentralWidget(central)
        self.setStatusBar(QStatusBar(self))
        self._retranslate_ui()
        self._sync_transport_ui()
        self._sync_role_ui()

    def _t(self, key: str, **values: Any) -> Any:
        return ui_text(self.language, key, **values)

    def _toggle_language(self) -> None:
        self.language = "en" if self.language == "zh" else "zh"
        self._retranslate_ui()

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(self._t("title"))
        self.language_button.setText(self._t("language_button"))
        self.load_button.setText(self._t("load_protocol"))
        self.settings_group.setTitle(self._t("connection"))
        self.role_label.setText(self._t("role"))
        self.role_combo.setItemText(0, self._t("host"))
        self.role_combo.setItemText(1, self._t("device"))
        self.transport_label.setText(self._t("transport"))
        self.transport_combo.setItemText(0, self._t("internal_transport"))
        self.transport_combo.setItemText(1, self._t("serial_transport"))
        self.endpoint_label.setText(self._t("endpoint"))
        self.refresh_button.setText(self._t("refresh"))
        self.virtual_ports_button.setText(self._t("virtual_ports"))
        self.baudrate_label.setText(self._t("baudrate"))
        self.bytesize_label.setText(self._t("data_bits"))
        self.parity_label.setText(self._t("parity"))
        for index, key in enumerate(("parity_none", "parity_even", "parity_odd", "parity_mark", "parity_space")):
            self.parity_combo.setItemText(index, self._t(key))
        self.stopbits_label.setText(self._t("stop_bits"))
        self.command_group.setTitle(self._t("commands"))
        self.command_table.setHorizontalHeaderLabels(self._t("command_headers"))
        self.command_detail.setPlaceholderText(self._t("select_command"))
        self.output_group.setTitle(self._t("traffic"))
        self.log_table.setHorizontalHeaderLabels(self._t("log_headers"))
        self.decoded_fields_label.setText(self._t("decoded_fields"))
        self.clear_button.setText(self._t("clear"))
        self.decoded_table.setHorizontalHeaderLabels(self._t("decoded_headers"))
        if self.connected:
            self.connect_button.setText(self._t("close"))
            self.connection_label.setText(self._t("opened"))
            endpoint = self._t("internal_name") if self.transport_combo.currentData() == "internal" else self.port_combo.currentText()
            self.statusBar().showMessage(self._t("connected", endpoint=endpoint))
        else:
            self.connect_button.setText(self._t("open"))
            self.connection_label.setText(self._t("closed"))
            if self.protocol:
                self.statusBar().showMessage(self._t("loaded_commands", count=len(self.protocol["commands"])))
            else:
                self.protocol_label.setText(self._t("no_protocol"))
                self.statusBar().showMessage(self._t("ready"))
        self._sync_role_ui()

    def _show_virtual_ports(self) -> None:
        dialog = VirtualPortDialog(self.language, self._refresh_ports, self)
        dialog.exec()
        self._refresh_ports()

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
            self._t("load_dialog_title"),
            start_dir,
            self._t("file_filter"),
        )
        if path:
            self._load_protocol_file(Path(path))

    def _load_protocol_file(self, path: Path) -> None:
        try:
            protocol = load_protocol(path)
        except ProtocolError as exc:
            QMessageBox.critical(self, self._t("protocol_error"), str(exc))
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
        self.statusBar().showMessage(self._t("loaded_commands", count=len(protocol["commands"])))

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
            self.command_action_button.setText(self._t("send_request"))
        elif self.transport_combo.currentData() == "internal":
            self.command_action_button.setText(self._t("simulate_request"))
        else:
            self.command_action_button.setText(self._t("send_response"))

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
            QMessageBox.warning(self, self._t("no_protocol_title"), self._t("no_protocol_message"))
            return
        transport = self.transport_combo.currentData()
        try:
            if transport == "serial":
                endpoint = self.port_combo.currentText().strip()
                if not endpoint:
                    raise ValueError(self._t("endpoint_required"))
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
            self.connect_button.setText(self._t("close"))
            self.connection_label.setText(self._t("opened"))
            self.connection_label.setStyleSheet("color: #176b70; font-weight: 700;")
            self.transport_combo.setEnabled(False)
            self.role_combo.setEnabled(False)
            self._sync_transport_ui()
            endpoint_name = self._t("internal_name") if transport == "internal" else self.port_combo.currentText()
            self.statusBar().showMessage(self._t("connected", endpoint=endpoint_name))
        except (serial.SerialException, ValueError, OSError) as exc:
            QMessageBox.critical(self, self._t("connection_failed"), str(exc))
            self.statusBar().showMessage(self._t("connection_failed_status", error=exc))

    def _close_connection(self) -> None:
        if self.serial_port is not None:
            try:
                self.serial_port.close()
            except serial.SerialException:
                pass
        self.serial_port = None
        self.connected = False
        self.rx_buffer.clear()
        self.connect_button.setText(self._t("open"))
        self.connection_label.setText(self._t("closed"))
        self.connection_label.setStyleSheet("")
        self.transport_combo.setEnabled(True)
        self.role_combo.setEnabled(True)
        self._sync_transport_ui()
        self.statusBar().showMessage(self._t("closed_status"))

    def _set_command_baudrate(self, command: dict[str, Any]) -> None:
        baudrate = command.get("baudrate", self._serial_defaults()["baudrate"])
        self.baudrate_spin.setValue(baudrate)
        if self.serial_port is not None:
            self.serial_port.baudrate = baudrate

    def _run_selected_command(self) -> None:
        command = self._selected_command()
        if not command:
            QMessageBox.information(self, self._t("no_command_title"), self._t("no_command_message"))
            return
        if not self.connected:
            QMessageBox.information(self, self._t("not_connected_title"), self._t("not_connected_message"))
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
                QMessageBox.information(self, self._t("no_response_title"), self._t("no_response_message"))
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
        command_name = command.get("name", self._t("unmatched")) if command else self._t("unmatched")
        values = [now, direction, command_name, format_hex(data), text_preview]
        for column, value in enumerate(values):
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            if column == 1:
                item.setForeground(Qt.GlobalColor.darkGreen if direction == "RX" else Qt.GlobalColor.darkBlue)
            self.log_table.setItem(row, column, item)
        self.log_table.scrollToBottom()
        self.statusBar().showMessage(
            self._t("traffic_status", direction=direction, count=len(data), command=command_name)
        )

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
        self.statusBar().showMessage(self._t("output_cleared"))

    def _report_runtime_error(self, error: Exception) -> None:
        QMessageBox.critical(self, self._t("serial_error"), str(error))
        self.statusBar().showMessage(self._t("error_status", error=error))

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
