# Serial Protocol Tester Skill / 串口协议转换 Skill

[中文](#中文) | [English](#english)

通用的 [Agent Skills](https://code.claude.com/docs/en/slash-commands) 格式 Skill，用于把串口协议文档、表格或示例报文转换成经过校验的 `serial_protocol.v1` JSON。独立的 PySide6 上位机项目位于 [serial-protocol-tester-app](https://github.com/10walnut/serial-protocol-tester-app)。

## 中文

### 能力

- 从协议资料提取波特率、帧结构、命令、应答、校验、大小端、比例和枚举。
- JSON 的名称、注释、字段作用和枚举只输出用户指定或原协议的单一语言。
- 对日期、时间、地址、传感器、设定值、标定值等非固定数据生成输入变量和安全计算公式。
- 为每个有意义的发送/接收字节定义位置、类型、作用和计算方法。
- 定义按帧头、长度连续拆包的规则，以及实时/历史等主动上报帧。
- 使用纯 Python 标准库校验生成的 JSON，不依赖 PySide6 上位机。

### 标准目录

```text
SKILL.md
references/protocol-script-format.md
scripts/protocol_core.py
scripts/validate_protocol.py
examples/sample_protocol.json
```

`SKILL.md` 只使用开放格式必需的 `name` 和 `description` 前置元数据。其他工具即使没有原生 Skill 安装器，也可以直接把 `SKILL.md` 及其引用文件作为上下文加载。

### 安装

先克隆仓库：

```powershell
git clone https://github.com/10walnut/serial-protocol-tester-skill.git
cd serial-protocol-tester-skill
```

Codex：

```powershell
.\install.ps1 -Target codex
```

Claude Code：

```powershell
.\install.ps1 -Target claude
```

Claude Code 会从 `~/.claude/skills/<skill-name>/SKILL.md` 发现个人 Skill，详见 [Claude Code Skills 官方文档](https://code.claude.com/docs/en/slash-commands)。

WorkBuddy：

```powershell
$env:WORKBUDDY_SKILL_DIRS = "C:\WorkBuddy\skills"
.\install.ps1 -Target workbuddy
```

不同 WorkBuddy 实现的目录可能不同，因此安装器优先读取 `WORKBUDDY_SKILL_DIRS`，也可显式传入：

```powershell
.\install.ps1 -Target workbuddy -Destination "D:\agent-skills\serial-protocol-tester"
```

Harness 或以项目 `skills/` 目录加载说明文件的编辑器：

```powershell
.\install.ps1 -Target harness
```

Harness 官方也支持直接克隆 Skill 仓库并在 Codex、Claude Code、Cursor、Copilot 或 Windsurf 中引用 `SKILL.md`，参见 [Harness Skills 文档](https://developer.harness.io/docs/platform/harness-ai/govern-ai-output/overview/)。

豆包、其他 Agent 或自定义目录：

```powershell
.\install.ps1 -Target custom -Destination "D:\your-agent\skills\serial-protocol-tester"
```

如果客户端不能扫描本地 Agent Skills 目录，直接上传/引用 `SKILL.md`，并允许它读取 `references/`、`scripts/` 和 `examples/`。仓库还提供 `AGENTS.md`、`CLAUDE.md` 和 `.github/copilot-instructions.md` 作为项目级发现入口。

Linux/macOS 使用：

```bash
./install.sh codex
./install.sh claude
./install.sh custom /path/to/agent/skills/serial-protocol-tester
```

### 使用

向 Agent 提供协议文件并要求使用 `serial-protocol-tester`。生成后运行：

```powershell
python .\scripts\validate_protocol.py .\my-protocol.json
```

需要按钮发送、虚拟串口和 TX/RX 逐字节解释时，使用配套的 [Serial Protocol Tester App](https://github.com/10walnut/serial-protocol-tester-app)。

## English

This repository is a standalone, portable Agent Skill that converts serial protocol documents into validated `serial_protocol.v1` JSON. It uses the standard `SKILL.md` structure and has no dependency on the GUI application.

Install it with `./install.sh codex`, `./install.sh claude`, or a custom destination. On Windows, use `install.ps1`. Tools without native Agent Skills discovery can load `SKILL.md` and its referenced resources directly.

The separate [Serial Protocol Tester App](https://github.com/10walnut/serial-protocol-tester-app) loads generated JSON and provides PySide6 host/device simulation, variable frame input, virtual COM support, stream framing, and TX/RX byte-level calculations.

MIT licensed.
