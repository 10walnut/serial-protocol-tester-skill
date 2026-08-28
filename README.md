# Serial Protocol Tester Skill / 串口协议测试 Skill

## 中文介绍

这是一个用于解决上下位机串口通讯测试麻烦问题的 Codex skill。它可以读取用户提供的串口通讯协议文档，整理为统一的 `serial_protocol.v1` JSON 脚本格式，并配套一个 PySide6 串口测试上位机示例程序。

主要能力：

- 将协议文档转换成标准化命令脚本。
- 保留命令原文、命令注释、波特率、串口参数、期望返回值和数据转换规则。
- 用 PySide6 上位机加载脚本，通过按钮发送/接收命令。
- 软件可作为上位机发送命令，也可作为下位机监听请求并自动回复。
- 支持 `loop://` 自测、真实串口，以及系统级成对虚拟 COM 口。
- 对校验算法、字节序、帧格式等影响通讯结果的不确定内容，会要求确认或在脚本中标记。

注意：普通桌面程序不能直接创建 Windows 内核级 COM 口。如果要让另一个独立上位机程序连接本工具，需要安装 com0com、厂商虚拟串口工具或使用真实串口线；本工具打开其中一个端口，待测程序打开另一个端口。

## English Introduction

Serial Protocol Tester is a Codex skill for simplifying host/device serial communication testing. It converts a user-provided serial protocol document into a standard `serial_protocol.v1` JSON script and includes a PySide6 serial console that can load the script for button-driven testing.

Core capabilities:

- Convert protocol documents into standardized command scripts.
- Preserve original command payloads, comments, baud rate, serial parameters, expected replies, and response decoding rules.
- Load scripts in a PySide6 console and send or receive commands from buttons.
- Run as a host/controller or as a device/target simulator with automatic replies.
- Support `loop://` self-tests, physical serial ports, and OS-level paired virtual COM ports.
- Flag or ask about uncertain protocol details such as checksum algorithms, byte order, frame delimiters, and variable fields.

Note: a desktop app cannot create kernel-level Windows COM ports by itself. To connect another independent application, install a paired virtual serial driver such as com0com or use physical serial hardware. This console opens one side of the pair while the application under test opens the other.

## Repository Layout

```text
serial-protocol-tester/
|-- SKILL.md
|-- agents/
|   `-- openai.yaml
|-- references/
|   `-- protocol-script-format.md
|-- scripts/
|   `-- validate_protocol.py
`-- assets/
    `-- pyside6-serial-console/
        |-- README.md
        |-- requirements.txt
        |-- sample_protocol.json
        `-- serial_console.py
```

## Use The Skill

Copy or clone the `serial-protocol-tester` folder into your Codex skills directory, then invoke:

```text
$serial-protocol-tester
请读取这个串口通讯协议文档，输出可用于 PySide6 串口测试上位机的 serial_protocol.v1 JSON 脚本。
```

Validate a generated script:

```bash
python serial-protocol-tester/scripts/validate_protocol.py path/to/protocol.json
```

## Run The PySide6 Console

```bash
cd serial-protocol-tester/assets/pyside6-serial-console
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python serial_console.py
```

For a quick self-test, load `sample_protocol.json`, choose `pyserial URL`, keep the port as `loop://`, and open the connection.
