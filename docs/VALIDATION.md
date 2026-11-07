# 整合验证记录

验证日期：2026-11-07。

## 自动化验证

- 后端：`python -m unittest discover -s tests -v` 通过，共 13 项。
- 覆盖：低风险放行、群发确认、外部指令阻断、删除拒绝、Windows 路径前缀、批准 / 拒绝、60 秒过期、重复决策冲突、普通任务、恢复流程和非法场景。
- 恢复流程验证三次失败、`INCIDENT_TRIGGERED`、`ACTION_CANCELLED`、`SNAPSHOT_RESTORED`、`RECOVERY_COMPLETED`，并断言文件恢复为原内容。
- 前端：`npx vue-tsc --noEmit` 通过。Live 创建任务请求已包含 `scenario`。
- 语法：`python -m compileall backend tests` 通过。

## 运行时边界

- FastAPI 依赖在当前受限环境中安装失败，因此没有在本轮完成 `uvicorn` 实际启动抓包；接口由 13 项服务测试和 `compileall` 覆盖。
- 前端生产构建和 Vitest 在当前执行环境的 Node 子进程权限下不可重复运行；此前前端验证记录显示本机构建和静态服务检查通过。
- API 状态在内存中保存，进程重启后清空；没有持久化数据库。
- 工具执行只修改 `MockWorkspace` 内存对象，不发送真实邮件或修改真实文件。

## 提交前人工复核

1. 启动 API 后确认 `/api/health` 返回 `ok`。
2. 在 Live 模式依次运行 normal、approval、block、recovery。
3. 审批批准和拒绝各验证一次；等待过期后再点击批准，确认不执行。
4. 检查用户名来自 `/api/me`，界面没有版本号。
5. 在常用浏览器宽度下检查控制台、轨迹、审批、恢复和评测页面。
