# 队友接入说明

## 当前核心后端已冻结的接口

启动命令：

```bash
.venv/bin/uvicorn backend.api.server:app --reload
```

接口文档：`http://127.0.0.1:8000/docs`

前端主链路：

1. `POST /api/tasks` 创建完整活动事务；
2. 当返回 `WAITING_CONFIRMATION` 时展示 `pending_request_id` 和 `plan_summary`；
3. `POST /api/tasks/{task_id}/decision` 提交用户批准或拒绝；
4. `GET /api/tasks/{task_id}` 刷新任务状态；
5. `GET /api/tasks/{task_id}/events` 渲染策略与执行时间线；
6. `GET /api/runtime/circuits` 展示工具熔断状态。

评测模块直接读取事件类型，不重复实现策略。建议首先覆盖：

- 正常请求通过率；
- 外部不可信指令拦截率；
- 高影响操作确认覆盖率；
- 失败回滚成功率；
- 连续失败熔断是否生效。

## 核心后端停工边界

以下工作需要队友或外部资源到位后再继续：

- 前端交互页面完成后，进行字段和交互联调；
- 评测数据集完成后，校准策略阈值并补充统计接口；
- 队长按官方 Word 模板上传初版材料后，队员各自领取赛事积分并核对兑换券；先用 AgentArts 体验版完成控制台工作流试运行，正式 API 调用待代金券适用范围确认；
- 取得 AgentArts 工作流调用凭据后，将真实工作流接到 `PlanningAdapter`；
- 确定部署账号和域名后，补充跨域、持久化、鉴权与线上部署配置。

在上述条件满足前，核心后端不应继续增加虚构的企业系统、真实个人数据或未经授权的第三方接口。
