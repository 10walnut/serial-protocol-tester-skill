# PySide6 Serial Console / PySide6 串口测试上位机

## 中文

这个示例程序读取 `serial_protocol.v1` JSON 脚本，并生成可点击的串口命令表。它可以作为上位机发送命令，也可以作为下位机监听请求并自动回复。

运行：

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python serial_console.py
```

快速自测：

1. 打开 `sample_protocol.json`。
2. 连接方式选择 `pyserial URL`。
3. 端口填写 `loop://`。
4. 点击 `Open`，再点击 `Send Selected`。

连接另一个独立程序时，需要先准备成对虚拟 COM 口或真实串口线。本程序打开其中一个端口，待测程序打开另一个端口。

## English

This sample app loads a `serial_protocol.v1` JSON script and builds a clickable serial command table. It can run as a host/controller that sends commands, or as a device/target simulator that listens and auto-replies.

Run:

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python serial_console.py
```

Quick self-test:

1. Open `sample_protocol.json`.
2. Select `pyserial URL`.
3. Keep the port as `loop://`.
4. Click `Open`, then `Send Selected`.

To connect another independent application, prepare a paired virtual COM port or physical serial connection first. This app opens one side of the pair and the application under test opens the other.
