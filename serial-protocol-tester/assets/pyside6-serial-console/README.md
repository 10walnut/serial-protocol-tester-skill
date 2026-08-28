# PySide6 Serial Console / PySide6 串口测试台

This application loads `serial_protocol.v1` JSON files and runs fixed command/response tests as either a host or a simulated device.

本程序加载 `serial_protocol.v1` JSON 协议文件，可作为上位机发送命令，也可作为下位机接收请求并自动应答。

界面默认使用中文。点击右上角 `EN` 切换为英文，点击 `中文` 切回中文。

## Transport modes / 通道模式

- **Internal virtual link / 内部虚拟链路**: no hardware or driver is required. Host requests receive configured mock responses; device mode simulates an incoming request and automatic reply inside the application.
- **COM port or serial URL / 串口或 URL**: connects to a physical COM port, one side of an installed virtual COM pair, or a pyserial URL such as `loop://`.

- **内部虚拟链路**：无需硬件和驱动，用于验证协议脚本、命令按钮和返回解析。
- **串口或 URL**：连接物理串口、已安装虚拟串口对的一端，或 `loop://` 等 pyserial URL。

Windows applications cannot expose a new COM device using PySide6 alone. The Virtual ports dialog can call an already installed com0com `setupc.exe` to create a linked pair after UAC approval. To test another upper-computer application, open one endpoint in that application and the paired endpoint here.

仅靠 PySide6 无法在 Windows 中注册新的 COM 设备。需要和另一款上位机软件联调时：先单独安装 [com0com](https://sourceforge.net/projects/com0com/)，再点击本程序的“虚拟串口”，通过已安装的 `setupc.exe` 创建 `COM10 ↔ COM11` 等端口对。创建时会出现 Windows 管理员权限确认；本程序不会自动下载或静默安装驱动。

## Start / 启动

From the repository root, double-click `start_serial_console.bat`, or run:

在仓库根目录双击 `start_serial_console.bat`，或执行：

```powershell
.\start_serial_console.ps1
```

The first run creates a local `.venv` and installs PySide6 and pyserial. Failures are written under `logs/`; the batch window pauses on errors instead of closing immediately.

首次启动会创建本地 `.venv` 并安装依赖。失败信息写入 `logs/`，批处理窗口会在错误时停住，不会直接闪退。
