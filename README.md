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

## 核心能力

- `ALLOW / CONFIRM / BLOCK` 确定性策略决策；
- 任务护照绑定工具、动作、参数和有效期，防止越权及重放；
- 审批摘要绑定，避免批准后偷偷换参数；
- 统一审计事件、模拟工具、失败恢复与熔断；
- Vue 3 可交互演示控制台；
- Live 模式可在提交前按本次任务参数预览最小工具范围和预计三态决策，修改参数后旧预览失效；
- Live 模式可检查一份脱敏 TXT/CSV 参考资料，记录来源与风险摘要，隔离正文和敏感行值；外部资料不能改变用户授权；
- 提交前可核对 CSV 行数与拟通知人数，提示人工处理差异与敏感列；建议只读，不自动扩权或改动任务参数；
- Live 模式按用户填写的活动参数生成三步事务与任务护照，支持连续审批及可追踪的执行结果；
- AgentArts 可接入的只读 Streamable HTTP MCP Server（策略预览、运行状态）与 ARM64 部署配置；智能体不能通过 MCP 自行批准或执行工具。

主链路命令行演示可用 `python3 scripts/run_task_demo.py`；`scripts/run_demo.py` 仅用于单独观察底层策略规则。

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

演示 API 仅在进程内保存状态，没有真实登录、持久化存储或多租户隔离，**不可直接作为公网可写服务部署**。公开给 AgentArts 的 MCP 入口只有只读预览和健康检查；人类审批只在演示后端处理。不连接真实学校系统、邮箱、支付账户或个人通讯录；接入真实系统前须完成身份认证、凭据管理、授权校验和安全评测。
