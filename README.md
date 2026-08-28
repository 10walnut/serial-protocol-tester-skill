# Serial Protocol Tester Skill / 串口协议测试 Skill

[中文](#中文介绍) | [English](#english)

## 中文介绍

这是一个面向上下位机串口联调的 Codex Skill 和 PySide6 桌面测试工具。Skill 可以读取用户提供的通信协议文档、表格或示例报文，将其整理为可校验的 `serial_protocol.v1` JSON 脚本；桌面程序加载脚本后，以按钮方式发送命令、模拟设备应答并解析返回数据。

主要能力：

- 上位机模式：发送协议命令并显示返回帧。
- 下位机模式：识别收到的请求并按脚本自动应答。
- 默认中文界面，右上角 `EN` 按钮可切换英文，再点 `中文` 可切回。
- 内部虚拟链路：无需硬件即可验证请求、应答和解析规则。
- 外部串口联调：支持物理 COM 口、已安装虚拟串口对以及 pyserial URL。
- 虚拟串口管理：检测已安装的 com0com，通过 UAC 创建两个互联的 COM 端口。
- 命令表：同时显示命令名称、原始 HEX、注释、波特率、预期返回和命令 ID。
- 数据转换：支持 HEX、ASCII、UTF-8、有符号/无符号整数、Float32、大小端、比例、偏移、单位和枚举。
- 校验和：支持 SUM8、XOR8 和 CRC-16/Modbus。
- Windows 启动与打包：自动创建虚拟环境；失败时保留窗口并写入 `logs/`。

### 快速开始

在 Windows 中双击：

```text
start_serial_console.bat
```

也可以在 PowerShell 中运行：

```powershell
.\start_serial_console.ps1
```

首次运行会在应用目录中创建 `.venv` 并安装 PySide6 Widgets 运行库、pyserial。若环境损坏：

```powershell
.\start_serial_console.ps1 -ResetVenv
```

只检查运行环境而不打开窗口：

```powershell
.\start_serial_console.ps1 -CheckOnly
```

构建单文件 EXE：

```powershell
.\build_serial_console.ps1
```

或双击 `build_serial_console.bat`。构建结果位于 `dist\SerialProtocolTester.exe`。使用 `-OneDir` 可生成目录模式。

### 虚拟串口说明

“内部虚拟链路”只在本程序内部模拟通信，不会向 Windows 注册 COM 设备。若需要让另一款上位机软件连接本模拟器：

1. 从 [com0com 官方项目](https://sourceforge.net/projects/com0com/) 安装虚拟串口驱动。
2. 在本程序点击“虚拟串口”，确认或选择 `setupc.exe`。
3. 输入两个未占用端口，例如 `COM10` 和 `COM11`，点击“创建端口对”并确认 Windows UAC。
4. 本程序选择“串口或 URL”并打开 `COM10`，另一款上位机打开 `COM11`。

本项目不会自动下载或静默安装内核驱动。com0com 在部分新版 Windows 环境可能受到驱动签名策略限制，此时需要使用组织批准且正确签名的虚拟串口驱动。

### 使用 Skill

将 `serial-protocol-tester` 目录作为 Codex Skill 使用，并向它提供协议文档。例如：

```text
使用 $serial-protocol-tester 读取我上传的串口协议，生成可校验的 JSON 协议脚本。
```

校验生成的协议文件：

```powershell
python .\serial-protocol-tester\scripts\validate_protocol.py .\my_protocol.json
```

协议格式说明见 [`protocol-script-format.md`](serial-protocol-tester/references/protocol-script-format.md)，可运行示例见 [`sample_protocol.json`](serial-protocol-tester/assets/pyside6-serial-console/sample_protocol.json)。

## English

This repository contains a Codex skill and a PySide6 desktop console for upper/lower-computer serial testing. The skill converts an uploaded protocol document, table, or sample frames into a validated `serial_protocol.v1` JSON script. The console loads that script and exposes each command as an interactive test action.

Key capabilities:

- Host mode sends protocol requests and decodes responses.
- Device mode matches incoming requests and sends scripted replies.
- The interface starts in Chinese and switches to English with the top-right language button.
- Internal virtual transport tests command/response behavior without hardware.
- External transport supports physical COM ports, installed virtual COM pairs, and pyserial URLs.
- The virtual-port dialog can invoke an installed com0com `setupc.exe` through Windows UAC to create a linked COM pair.
- The command table shows original bytes, annotations, baud rate, expected response, and command ID.
- Decoders support hex, ASCII, UTF-8, signed and unsigned integers, Float32, endianness, scaling, offsets, units, and enums.
- Checksums include SUM8, XOR8, and CRC-16/Modbus.
- Windows launch and packaging scripts create an isolated environment and keep errors visible with log files.

### Quick start

Double-click `start_serial_console.bat`, or run:

```powershell
.\start_serial_console.ps1
```

Use `.\start_serial_console.ps1 -CheckOnly` to verify the environment without opening the GUI.

Build a single-file Windows executable with:

```powershell
.\build_serial_console.ps1
```

The internal transport is process-local. To test another application, install com0com separately, open the Virtual ports dialog, create a pair such as `COM10 ↔ COM11`, then open one endpoint in this console and the other in the external application. The project does not silently download or install kernel drivers.

## Repository layout

```text
serial-protocol-tester/
├── SKILL.md
├── agents/openai.yaml
├── references/protocol-script-format.md
├── scripts/
│   ├── validate_protocol.py
│   └── test_protocol_core.py
└── assets/pyside6-serial-console/
    ├── protocol_core.py
    ├── serial_console.py
    ├── sample_protocol.json
    └── requirements.txt
```

Licensed under the MIT License.
