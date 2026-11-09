# 御界 AgentGuard

面向工具型智能体的可信执行守护系统。项目在 Agent 与 MCP 工具之间增加确定性执行边界：

- `ALLOW`：符合授权的低风险操作直接执行；
- `CONFIRM`：群发、敏感数据等高影响操作等待人工确认；
- `BLOCK`：越权、外部诱导或危险参数在工具执行前被阻止；
- 统一 Trace：记录请求、决策、证据、审批和执行结果；
- 熔断恢复：达到失败阈值后取消后续动作并恢复快照。

## 快速验证

核心原型使用 Python 3.9+ 标准库：

```bash
python scripts/run_demo.py
python -m unittest discover -s tests -v
```

当前分支包含 13 项后端测试，覆盖策略放行、群发确认、外部指令阻断、删除拒绝、审批拒绝、过期取消、重复审批冲突和三次失败后的快照恢复。

## 运行演示 API

```powershell
python -m pip install -e ".[api]"
uvicorn backend.api.server:app --reload --port 8000
```

`docs/api.md` 描述任务、审批、事件、恢复和用户接口。API 使用进程内存保存演示状态，并通过 `PolicyEngine` / `MCPGateway` 执行所有工具请求。

## 运行 Web 控制台

```powershell
cd frontend
npm install
npm run dev
```

默认 Mock 模式可独立演示。联调演示 API 时创建 `frontend/.env.local`：

```env
VITE_DATA_MODE=live
VITE_API_BASE_URL=http://127.0.0.1:8000
```

前端细节见 `frontend/README.md`，演示步骤见 `docs/DEMO.md`。

## 目录

```text
backend/
├── agent_core/          # Agent 编排适配层
├── api/                 # FastAPI 演示服务与公共协议
├── services/            # 任务、审批和恢复编排
├── policy_engine/       # 权限、参数和三态决策
├── mcp_gateway/         # 工具注册、执行拦截与审批
├── mock_tools/          # 日程、通知、共享文件等模拟工具
├── recovery/            # 快照与状态恢复
└── models/              # 领域模型与事件结构
config/                  # 策略配置
docs/                    # 架构、API、联调和演示说明
evaluation/              # 评测团队工作区
frontend/                # Vue 3 控制台
tests/                   # 核心与编排自动化测试
```

## 安全边界

当前版本只操作脱敏模拟数据，不连接真实学校系统、邮箱、支付账户或个人通讯录。演示 API 没有真实登录、持久化存储和多租户隔离。任何外部系统接入前，必须补充授权、凭据存储、权限校验和测试环境说明。

## 开发分支

- `main`：可演示稳定版本；
- `develop`：日常集成；
- `feature/agent-core`、`feature/policy-mcp`：核心后端；
- `feature/web-console`：前端控制台；
- `feature/web-console-integration`：本整合分支。
