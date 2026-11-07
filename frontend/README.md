# 御界 AgentGuard Web 控制台

Vue 3 + TypeScript + Pinia + Vue Router，黑 / 白 / 灰界面。默认使用明确标注的本地 Mock；Live 模式连接仓库内的 FastAPI 演示 API。

## 启动

```powershell
cd ..
python -m pip install -e ".[api]"
uvicorn backend.api.server:app --reload --port 8000

cd frontend
npm install
npm run dev
```

开发服务器地址是 `http://127.0.0.1:5173`。需要 Live 模式时创建 `.env.local`：

```env
VITE_DATA_MODE=live
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Live 失败会显示后端错误，不会自动退回 Mock。左侧用户名读取 `/api/me`，界面不展示版本号。

## 功能

- 任务控制台：任务标题、描述、四类演示场景、附件信息、授权范围和列表筛选。
- 执行轨迹：事件时间线、筛选、结构化请求、策略证据、JSON 导出。
- 人工审批：影响范围、完整工具参数、来源与规则、批准 / 拒绝、审批历史。
- 事件与恢复：三次失败后熔断、取消后续通知、快照前后比较、恢复动作记录。
- 评测看板：60 条合成样例、指标公式、三组对照、筛选和分页。

Mock 模式支持暂停、继续、倍速和本地刷新恢复；这些回放控制不会改变真实 API 状态。

## 范围说明

当前控制台是比赛演示界面。Mock 中的策略结果由预置场景产生；Live 中的决策和执行来自仓库内的 `PolicyEngine` / `MCPGateway`，但业务工具仍是内存 Mock。任务描述不会调用模型，附件只记录元数据，不读取内容；不会发送真实通知或修改真实共享文件。

评测数值全部来自合成数据，不能作为实际效果。真实登录、持久化、多用户授权、真实业务工具和审计存储由后续后端迭代接入。

## 质量检查

```powershell
npm run build
npm test
npx vue-tsc --noEmit
```

接口契约见根目录 `docs/api.md` 和 `docs/INTEGRATION.md`。演示流程见根目录 `docs/DEMO.md`。
