# Serial Protocol Tester Skill / 串口协议转换 Skill

[中文](#中文) | [English](#english) | [PySide6 上位机](https://github.com/10walnut/serial-protocol-tester-app)

通用 Agent Skill：读取用户提供的串口协议文档、表格和示例报文，输出可校验、可执行的单语言 `serial_protocol.v1` JSON。仓库不依赖 GUI，可安装到 Codex、Claude Code、WorkBuddy、Harness，也可作为资料上传给豆包或其他 Agent。

## 中文

### 能力范围

- 提取串口参数、帧头、长度、命令、应答、校验、大小端、比例、单位和枚举。
- 名称、注释、字段作用和枚举只输出用户要求的一种语言，不在同一 JSON 中混合中英文。
- 日期、时间、地址、传感器、设定值和标定值使用变量与受限公式，不用无法解释的固定示例替代动态数据。
- 为发送与接收字段提供字节位置、类型、作用、换算公式和校验覆盖范围。
- 描述一条请求对应多条回复：立即 ACK、延迟回复、固定次数回复、100 ms 等周期数据流及停止命令。
- 描述主动上报和历史数据帧；重复记录共用字段定义，避免重复几十次相同说明。
- 使用纯 Python 标准库校验 JSON，不依赖 PySide6 软件。

### 仓库结构

```text
SKILL.md                              Agent 执行说明
references/protocol-script-format.md  完整 JSON 格式与示例
scripts/protocol_core.py              组帧、公式、校验与协议校验核心
scripts/validate_protocol.py          命令行校验器
examples/sample_protocol.json         可直接运行的示例协议
install.ps1 / install.sh              多客户端安装脚本
```

### 安装

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

WorkBuddy：

```powershell
$env:WORKBUDDY_SKILL_DIRS = "C:\WorkBuddy\skills"
.\install.ps1 -Target workbuddy
```

也可以显式指定目录：

```powershell
.\install.ps1 -Target workbuddy -Destination "D:\agent-skills\serial-protocol-tester"
```

Harness 或使用项目 `skills/` 目录的工具：

```powershell
.\install.ps1 -Target harness
```

豆包或其他客户端：

```powershell
.\install.ps1 -Target custom -Destination "D:\your-agent\skills\serial-protocol-tester"
```

不能扫描本地 Skill 目录的客户端，可以上传 `SKILL.md`、`references/protocol-script-format.md` 和协议原文，并要求严格按 Skill 输出 JSON。Linux/macOS 使用 `./install.sh codex`、`./install.sh claude` 或 `./install.sh custom <目录>`。

### 使用教程

1. 向 Agent 上传协议文档、命令表、抓包或示例帧。
2. 指定输出语言，例如“只输出中文 JSON，不要中英混合”。
3. 说明需要模拟的角色和时序，例如“启动命令先回复 ACK，再每 100 ms 回复实时数据，停止命令结束数据流”。
4. 要求 Agent 使用 `serial-protocol-tester` Skill 生成 JSON，并列出无法从文档确定的事实。
5. 运行校验器，必须修复所有错误后再导入软件。

示例提示词：

```text
使用 serial-protocol-tester Skill 读取我上传的协议，只输出中文 serial_protocol.v1 JSON。
开启实时模式后先回复确认帧，100ms 后开始周期发送实时数据，直到停止命令。
日期时间使用系统默认值；重量、加速度和角速度提供可输入变量与协议换算公式。
每个有意义的发送和接收字节都要写明作用，生成后运行校验器。
```

校验：

```powershell
python .\scripts\validate_protocol.py .\my-protocol.json
python -m unittest discover -s tests -p "test_*.py" -v
```

### 多回复 JSON 规则

`response` 是立即确认帧。`follow_up_replies` 是确认后的附加回复；周期回复必须有 `interval_ms` 和稳定的 `stream_id`。`repeat_count: 0` 表示持续发送，直到另一命令通过 `stop_streams` 停止。

```json
{
  "response": {"encoding": "hex", "data": "AA 55 81 01 00"},
  "follow_up_replies": [
    {
      "frame_ref": "realtime_data",
      "delay_ms": 100,
      "interval_ms": 100,
      "repeat_count": 0,
      "stream_id": "realtime",
      "prompt_variables": true
    }
  ],
  "auto_reply": true
}
```

`frame_ref` 指向顶层 `frames`。用于下位机模拟的主动帧必须提供完整 `simulation`，其中可定义 `variables`、`encode`、`formula` 和 `checksum`。`prompt_variables: true` 让软件在启动流之前询问模拟值；省略时软件按默认值自动生成每一帧。

### 与上位机软件配合

Skill 负责从资料生成协议脚本，不创建 Windows 设备，也不要求安装 PySide6。需要按钮收发、虚拟 COM、下位机自动应答和逐字节解释时，下载独立的 [Serial Protocol Tester App](https://github.com/10walnut/serial-protocol-tester-app)。App 仓库包含完整教程、已签名 com0com 官方下载链接和虚拟端口排错方法。

## English

This portable Agent Skill converts serial specifications, tables, captures, and sample frames into validated `serial_protocol.v1` JSON. It preserves documented framing and timing, emits one requested language per file, creates editable variables and safe formulas for dynamic values, and describes every meaningful TX/RX byte.

It supports one-request-to-many-response workflows: an immediate `response`, delayed or periodic `follow_up_replies`, reusable active-frame `simulation`, and `stop_streams`. Periodic frames can prompt for sensor values before transmission or evaluate defaults automatically for every frame.

Install with `install.ps1 -Target codex`, `claude`, `workbuddy`, `harness`, or `custom`. On Linux/macOS, use `install.sh`. Clients such as Doubao that do not discover Agent Skills can load `SKILL.md` plus `references/protocol-script-format.md` directly.

After generation, run `python scripts/validate_protocol.py <file.json>`. For interactive host/device simulation, formula input, virtual COM pairs, scheduled replies, and byte-level traffic explanations, use the separate [Serial Protocol Tester App](https://github.com/10walnut/serial-protocol-tester-app).

Maintained by `十个核桃 / 10walnut`. MIT licensed.
