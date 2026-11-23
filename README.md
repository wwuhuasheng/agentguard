# 御界 AgentGuard

面向工具型智能体的可信执行守护系统。在 Agent 与 MCP 工具之间提供确定性策略、任务护照、人工审批、审计追踪和失败恢复。当前版本使用脱敏模拟数据，供比赛开发与演示。

## 本地运行

Python 3.9+：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[api,dev]'
python3 -m unittest discover -s tests -v
```

演示控制台使用的 HTTP API：

```bash
uvicorn backend.api.server:app --reload --port 8000
```

另开终端运行前端：

```bash
cd frontend
npm ci
npm run dev
```

前端默认使用 Mock 数据。连接本地 API 时，在 `frontend/.env.local` 中配置：

```env
VITE_DATA_MODE=live
VITE_API_BASE_URL=http://127.0.0.1:8000
```

`backend.api.server:app` 是统一启动入口：控制台接口位于 `/api/*`，原有核心事务接口位于 `/core/api/*`，两者在同一进程共享策略网关。独立运行 `backend.api.app:app` 仅用于核心接口开发和测试。已提供 AgentArts 工作流调用桥接代码，**尚未使用真实账号完成云端验证**；默认仍使用本地规划器。接入步骤见 [docs/agentarts-integration.md](docs/agentarts-integration.md)，前端演示见 [docs/DEMO.md](docs/DEMO.md)。

需要让多位评委或测试者同时试用模拟工具时，可设 `AGENTGUARD_DEMO_ISOLATION=1` 启动统一 API。此模式按浏览器会话隔离任务、审批和模拟工具状态，并关闭 `/core/*`；前端 Live 请求会携带会话 Cookie。启动与边界见 [docs/api.md](docs/api.md)。

## 核心能力

- `ALLOW / CONFIRM / BLOCK` 确定性策略决策；
- 任务护照绑定工具、动作、参数和有效期，防止越权及重放；
- 审批摘要绑定，避免批准后偷偷换参数；
- 统一审计事件、模拟工具、失败恢复与熔断；
- Vue 3 可交互演示控制台；
- Live 模式可在提交前按本次任务参数预览最小工具范围和预计三态决策，修改参数后旧预览失效；
- 版本化规则说明为预览结果提供处理建议和规则引用，并通过只读 MCP `explain_policy` 供 AgentArts 后续查询；
- Live 模式可同时检查一份脱敏 TXT 策划书与一份 CSV 报名表，分别记录来源与风险摘要，隔离正文和敏感行值；外部资料不能改变用户授权；
- 提交前可核对 CSV 行数与拟通知人数，并从标准可参与时段生成匿名排班草案；用户明确采纳后，服务端复核资料哈希和排班完整性，经共享文件审批才写入匿名行号与时段，不使用姓名电话或自动扩权；
- 可从格式明确的脱敏 TXT 策划资料提取活动时间和地点草案，经用户点击核对采纳后才填入表单；通知对象与权限仍由用户指定；
- Live 模式按用户填写的活动参数生成两/三步事务与任务护照；可取消共享文件更新权限，并支持连续审批及可追踪的执行结果；
- 人工审批前展示模拟文件差异或通知影响范围；目标文件在等待期间变化时，旧审批失效且不会覆盖较新版本；
- Live 轨迹页可导出服务端生成的脱敏证据包，并用离线脚本校验事件链和授权到执行的顺序；
- AgentArts 可接入的只读 Streamable HTTP MCP Server（策略预览、运行状态）与 ARM64 部署配置；智能体不能通过 MCP 自行批准或执行工具。

主链路命令行演示可用 `python3 scripts/run_task_demo.py`；`scripts/run_demo.py` 仅用于单独观察底层策略规则。

## 参赛资料

- [项目策划案](docs/competition/御界AgentGuard项目策划案.md)和[团队分工](docs/competition/御界AgentGuard团队分工.md)
- [初赛提交前复盘](docs/competition/御界AgentGuard初赛提交前复盘.md)和[初赛上传清单](docs/competition/御界AgentGuard初赛上传清单.md)
- [初赛作品信息表填表稿](docs/initial-submission-draft.md)和[演示视频脚本](docs/initial-demo-storyboard.md)
- [AgentArts 联调说明](docs/agentarts-integration.md)和[评测说明](evaluation/README.md)

## 目录

```text
backend/             # Agent 编排、策略、网关、API 与模拟工具
config/              # 策略配置
deploy/mcp_server/   # MCP Server 和部署配置
docs/                # 架构、接口与演示说明
evaluation/          # 评测工作区
examples/            # 虚构、脱敏的演示参考资料
frontend/            # Vue 3 控制台
tests/               # 自动化测试
```

## 安全边界

演示 API 仅在进程内保存状态；可选访客会话只解决多人演示时的误操作串扰，**不是实名登录或可持久化的多租户授权**。尚不可直接作为接入真实工具的公网可写服务部署。公开给 AgentArts 的 MCP 入口只有只读预览、规则解释和健康检查；人类审批只在演示后端处理。不连接真实学校系统、邮箱、支付账户或个人通讯录；接入真实系统前须完成身份认证、凭据管理、授权校验和安全评测。
