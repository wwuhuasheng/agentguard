# 2026—2027华为ICT大赛赛题2就绪度

## 硬性要求核对

| 要求 | 当前状态 | 下一验收证据 |
| --- | --- | --- |
| 基于AgentArts构建、编排与部署 | 进行中 | 多智能体画布、已部署版本、运行时地址 |
| 可视化Demo页面 | 本地页面与 Live 参数任务链路完成，在线部署待做 | 在线地址与三分钟演示视频 |
| Agent设计与工具编排 | MCP服务、ARM64镜像与本地协议实测已完成 | AgentArts工具卡片与云端调用链 |
| 知识接入 | 待设计 | 安全规则知识库及引用证据 |
| 多Agent协作 | 本地协议完成，云端待建 | 三Agent运行Trace |
| 效果评估 | 待成员C实现 | 评测集、基线对比、AgentArts评估报告 |
| 初赛材料可复现 | 46 项后端测试、25 项前端测试、构建和本地 MCP 协议验证通过 | AgentArts 云端调用录像与演示视频 |

## 先上传材料再领取赛事资源

赛题 1、赛题 2 参赛队员的资源通知要求：队伍完成报名组队、至少一名队员按官方 Word 模板上传一次有效初赛材料、队员本人完成华为云实名认证，之后才进入每周白名单核验。2026 年 12 月 9 日 17:00 是代金券资格的最后一次名单导出。首次上传不要求完整作品或 Demo 链接；可继续修改，初赛评分以作品截止前最后一次提交为准。每位符合条件的队员独立领取 350 积分，经开发者成长中心兑换代金券；积分并非等值现金，也不能假设不同账号可以合并使用。

已根据本机下载的**赛题 2 官方 Word 模板**生成项目内容草稿，存放在工作区 `outputs` 目录，尚缺队伍实名信息、联系方式和团队合照；由队长核对并上传。文字来源见 [`initial-submission-draft.md`](initial-submission-draft.md)，办理步骤见 [`competition-resource-claim.md`](competition-resource-claim.md)。本地文件不是平台上传回执。

## 初赛材料必须呈现

- 真实需求与目标用户；
- 作品简介和核心创意；
- Agent设计方案与工作流架构；
- 模型、知识库、MCP和其他资产选择；
- 基于AgentArts构建并运行的完整流程；
- 基于AgentArts真实构建与运行的Demo视频（首次为领取资源而上传的材料可不含完整作品或Demo链接，初赛最终版仍需补齐）；
- 团队分工。

## 当前主创新点

“任务护照”在任务开始时生成最小、限时、参数级授权。外部内容和模型后续推理只能提供信息，不能增加工具、字段、接收对象或影响范围。高影响操作还需经过与请求摘要绑定的人工确认。

## 已完成的可复现证据

- `linux/arm64` MCP镜像可完成构建；
- `/ping`返回服务状态和七个注册工具；
- MCP `initialize`协商成功，协议版本为`2025-03-26`；
- `tools/list`成功返回七个带输入输出Schema的工具；
- `tools/call`可调用`runtime_status`；
- 端到端校园活动样例在完成低风险步骤后停在`WAITING_CONFIRMATION`，未直接执行文件更新和群发通知。
- 任务护照授权不可重放，普通HTTP API不暴露绕过护照的原始工具入口。
- 前端 Live 模式可提交结构化活动参数并展示规划证据与护照；默认规划器仍是本地离线适配器。
- 2026 年 11 月 10 日复测：后端 46 项、前端 25 项测试和前端生产构建通过。

## 暂不能宣称完成的能力

- 尚未在AgentArts控制台创建和部署真实多智能体；
- 尚未完成AgentArts平台评估；
- 当前MCP服务已完成本地镜像与协议验证，但尚未完成华为云SWR和AgentArts运行时上的`tools/list/tools/call`验证；
- 当前模拟工具不等同于真实学校、社区或企业系统接入。

## 比赛要求复核依据

- [华为ICT大赛创新赛中国区官方赛题入口](https://e.huawei.com/cn/talent/#/ict/innovation-details?zoneCode=027425&zoneId=98269700&compId=85132021&divisionName=%E4%B8%AD%E5%9B%BD%E5%8C%BA&type=C002)
- [赛事资源积分领取入口](https://gallery.developer.huaweicloud.com/gallery/competition?type=innovation)
- [初赛作品上传操作指导](https://e.huawei.com/cn/talent/news/#/details?consultationId=5970)
- [大连理工大学2026—2027华为ICT大赛通知](https://chuangxin.dlut.edu.cn/info/1020/16867.htm)
- [AgentArts MCP Server镜像开发说明](https://support.huaweicloud.com/highcode-agentarts/agentarts_10_080.html)
- [AgentArts MCP Server运行时部署说明](https://support.huaweicloud.com/highcode-agentarts/agentarts_10_127.html)
