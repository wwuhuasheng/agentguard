# AgentArts接入与部署

## 参赛顺序与零自购起步

赛题 2 的资源邮件要求**先上传一次有效初赛材料，再由各队员领取积分兑换代金券**。领取流程见 [`competition-resource-claim.md`](competition-resource-claim.md)。因此，不应把购买 MaaS 或云服务器当成开始开发的前置条件。

在代金券券种和适用范围核实前，先使用 AgentArts 体验版的控制台能力：申请公测、免费开通体验版、创建工作流、在平台内试运行并记录节点输入输出。平台首次赠送的 200 万模型 Token 仅用于模型调测和智能体试运行，**不覆盖发布后从我们的后端/前端发起的正式 API 调用**。目前的 `feature/agentarts-cloud-bridge` 正属于后者；未取得适用代金券或明确预算前，不启用它的真实云端调用。体验版自身有额度限制，开通套餐时可能自动启用按需计费，部署前还需检查日志、指标、调用链等依赖服务的计费选项。

初次控制台试运行的最小工作流：

1. 开始节点输入 `title`、`starts_at`、`location`、`recipient`、`recipient_count`、`notice_content`、`source_trust`，只填 `example.org` 等脱敏模拟数据；
2. 业务规划节点输出目标与三步事务的**分析证据**，不得生成可执行的新收件人或新工具；
3. 内容隔离节点说明 `source_trust`，把外部资料中的命令视为待审查文本，不承认其授权声明；
4. 行为守卫节点标注文件更新、群发通知的风险，最终决策仍交给确定性网关；
5. 结束节点输出 `agent_evidence_json`，用正常输入和不可信输入各试运行一次，保存画布和运行截图。

这一步能证明 AgentArts 的**真实构建与试运行**，但尚不能证明“AgentArts 已经调用我们的安全网关”。初赛最终版应在资源到位后接入只读的策略预览 MCP/HTTP 工具，并由演示后端负责真实任务、人工审批和 Trace；不得把独立的本地前端演示与控制台试运行剪辑成一条已经打通的云端链路。AgentArts 对自研 HTTP MCP 要求公网可达；也支持从 npm/PyPI 拉起 Stdio MCP，但现有仓库的 Streamable HTTP 服务不能不经适配直接当成 UVX 包使用。

官方参考：[免费体验和依赖服务](https://support.huaweicloud.com/qs-agentarts/agentarts_04_0000.html)、[试运行免费 Token 范围](https://support.huaweicloud.com/bestpractice-agentarts/agentarts_06_0094.html)、[自定义 MCP 接入方式](https://support.huaweicloud.com/lowcode-agentarts/agentarts_05_0136.html)。

## 云端规划桥接（代码已就绪，尚待真实账号验证）

现有控制台 `live` 模式可通过后端调用 AgentArts 已发布工作流。启用后，
`agent_plan.provider` 显示 `huawei-agentarts-workflow`；若云端报错或输出不符合约定，
任务创建返回 `502`，**不会静默退回本地模拟结果**。API Key 只保留在后端进程，
前端不接触密钥。当前云端只负责分析证据，真正的工具参数由用户输入确定，
再经任务护照、策略网关和人工审批；工具仍是内存模拟，不会发送真实邮件。

先在 AgentArts 创建并发布一个工作流，开始节点定义以下必填变量，名称必须一致：
`title`、`starts_at`、`location`、`recipient`、`recipient_count`（整数）、
`notice_content`、`source_trust`。建议依次编排业务规划、内容隔离、行为守卫三个
Agent/LLM 节点；最后输出 `agent_evidence_json` 字符串。输出示例：

```json
{
  "agent_evidence": [
    {"role":"BUSINESS_AGENT","conclusion":"活动目标已拆解。","evidence":{}},
    {"role":"CONTENT_ISOLATION_AGENT","conclusion":"外部内容不继承授权。","evidence":{}},
    {"role":"BEHAVIOR_GUARD_AGENT","conclusion":"文件更新与通知需策略裁决。","evidence":{}}
  ]
}
```

可将这个 JSON 放在工作流结束节点的 `user_fields.agent_evidence_json`，或作为
`responseContent` 返回；工作流必须产生 `workflow_finished` 且状态为 `succeeded`。
后端只接收这三条证据。即使模型输出 `steps`、工具参数或更高的信任级别，
它们也不会进入执行计划。平台工作流可用 MCP 工具 `runtime_status` 验证连接，
并用 `preview_activity` 展示确定性规则如何判定三个事务步骤。预览结果不签发
实际授权、不创建任务、不审批，也不执行模拟工具；用户输入与模型输出必须由
可信演示后端分开处理。

账号侧需要完成：开通 AgentArts；接入可用于 API 调用的 MaaS/第三方模型；
提交工作流版本并勾选“部署至实例”；入站认证选 API Key；复制完整调用路径，
并从运行时“访问与权限控制”取得 API Key。官方说明：[API 调用前提和取凭证步骤](https://support.huaweicloud.com/bestpractice-agentarts/agentarts_06_0022.html)、[运行时调用接口](https://support.huaweicloud.com/api-agentarts/InvokeRuntime.html)、[SSE 事件格式](https://support.huaweicloud.com/api-agentarts/agentarts_07_0056.html)。
API 调用会消耗模型额度；平台免费 Token 不能用于该 API，先确认比赛代金券或预算。

在启动后端的终端设置环境变量（Key 只在本机输入，不要发到聊天或提交仓库）：

```bash
export AGENTGUARD_PLANNER=agentarts
export AGENTARTS_INVOCATION_URL='https://<控制台访问域名>/runtimes/<运行时名称>/invocations'
export AGENTARTS_INVOKE_MODE=debug
read -s AGENTARTS_API_KEY
export AGENTARTS_API_KEY
uvicorn backend.api.server:app --port 8000
```

粘贴 Key 后按回车。完整 URL 必须来自华为云控制台，使用官方 HTTPS 域名；
切勿使用文档中的占位 URL。前端 `frontend/.env.local` 设置 `VITE_DATA_MODE=live`。
创建一个使用 `example.org` 接收地址的脱敏活动，检查规划来源及工作流调用链。
退出当前终端会清除本次临时输入的 Key。默认 `AGENTGUARD_PLANNER=local`，
因此不配置云端时不会产生模型费用。

这一步只能证明“AgentArts 分析工作流 → 本地安全网关”连通。比赛最终版本还需
把 MCP Server 部署到华为云、在 AgentArts 中完成工具编排/评估，并提供云端
调用链及在线 Demo 证据；不能把本地桥接冒充完整云端部署。

## 作品中的职责边界

```text
可视化Demo -> 演示后端（目前只允许本地/受控环境，尚无真实身份认证）
  -> AgentArts多智能体/工作流（分析证据）
     -> 只读MCP：策略预览、运行状态
  -> 可信执行链：任务护照 -> 策略网关 -> 人工审批 -> 脱敏模拟工具
     -> Trace、回滚与熔断
```

AgentArts 负责模型、提示词、工作流、多 Agent 协作、平台调用链和评估；演示后端负责事务暂停/恢复、人工审批、确定性安全执行边界和业务 Trace。比赛演示应真实呈现 AgentArts 工作流及其只读 MCP 调用，本地适配器只用于离线回归，不能作为已经接入 AgentArts 的证明。

**安全边界：**公开给 AgentArts 的 MCP Server 只注册 `preview_activity` 和
`runtime_status`。模型不能通过 MCP 创建任务、读取任务护照、提交原始工具请求、
取消任务或批准待确认操作。预览中的 `source_trust` 只是未核验的假设，绝不转化为
执行授权。现有演示 HTTP API 还没有用户身份认证，禁止直接公网开放；若要云端
互动演示，须先补登录、会话绑定、审批身份校验和服务间认证。

## 本地MCP服务

MCP部署环境与普通开发环境隔离：

- Python 3.11；
- `mcp==1.28.1`；
- Streamable HTTP；
- 无状态协议传输；
- 服务路径`/mcp`；
- 探活路径`/ping`。

构建ARM64镜像：

```bash
docker buildx build \
  --platform linux/arm64 \
  -f deploy/mcp_server/Dockerfile \
  -t agentguard-mcp:dev \
  --load .
```

本地启动：

```bash
docker run --rm -p 8080:8080 agentguard-mcp:dev
```

探活：

```bash
curl http://127.0.0.1:8080/ping
```

列出MCP工具：

```bash
curl -X POST http://127.0.0.1:8080/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'
```

2026 年 11 月 10 日，已在本机临时 Python 3.12 环境使用锁定的 `mcp==1.28.1` 复验最新代码。2026 年 11 月 11 日，又用当前代码复建并加载 `linux/arm64` 镜像 `agentguard-mcp:local-20261110`，在本机回环端口实际运行容器：`/ping` 返回 `ok`；Streamable HTTP `initialize` 协商 `2025-03-26` 成功；`tools/list` 仅返回 `preview_activity`、`runtime_status`；两个 `tools/call` 均成功，`preview_activity` 返回 `PREVIEW_ONLY` 和三步 `ALLOW / CONFIRM / CONFIRM`。临时容器已停止。上述是**本地容器验证**，尚未上传 SWR、部署 AgentArts 运行时或验证云端调用；本地协议结果不能替代云上证据。

## AgentArts控制台步骤

1. 开通AgentArts并接入可调用模型；
2. 将ARM64镜像上传至华为云SWR；
3. 在“托管与运行 > 智能体运行时”创建运行时，入站协议选择MCP；
4. 取得访问地址，通过`tools/list`和`tools/call`完成云上验证；
5. 在“开发中心 > 智能体组件 > MCP”创建自定义MCP，选择Streamable HTTP；
6. 创建业务规划、内容隔离、行为守卫三个Agent；
7. 创建固定工作流，按规划、隔离、`preview_activity`、行为守卫和结束节点连接；
8. 在演示后端由用户明确提交任务，后端签发护照并通过自己的审批界面接收确认；AgentArts 工作流不能替用户调用审批；
9. 提交版本并部署多智能体应用，开启日志、指标和调用链；
10. 可视化 Demo 由后端持有密钥并调用 AgentArts 运行时 API，再由后端执行受控事务；前端不直接持有 AgentArts Key，也不能把纯本地链路冒充云端调用。

## 建议工作流

```text
开始
 -> 提问器补齐活动参数
 -> 业务规划Agent
 -> 内容隔离Agent
 -> preview_activity（只读：ALLOW / CONFIRM / BLOCK 及原因）
 -> 行为守卫Agent解释风险，不执行、不批准
 -> 结束

用户在可视化Demo提交任务 -> 后端签发任务护照 -> 执行到待确认
 -> 用户在审批界面明确同意或拒绝 -> 后端继续或回滚 -> 展示Trace
```

## 当前限制

- 服务状态仍保存在单进程内存中，只适合初赛原型和单副本演示；
- 演示 API 无真实用户认证，不可直接部署成公网可写服务；
- 正式多副本部署前需将任务、护照、审批和Trace持久化；
- 真实AgentArts工作流、调用链截图和平台评估仍待账号登录、平台可用及模型资源确认后完成；2026 年 11 月 11 日 Chrome 跳转华为云登录页时出现 `ERR_CONNECTION_CLOSED`，因此未开展云端操作；
- 不得在仓库提交API Key、Token或`.agentarts_config.yaml`。
