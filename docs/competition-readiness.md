# 2026—2027华为ICT大赛赛题2就绪度

## 硬性要求核对

| 要求 | 当前状态 | 下一验收证据 |
| --- | --- | --- |
| 基于AgentArts构建、编排与部署 | 本地桥接代码已有，真实平台构建尚未完成 | 多智能体画布、已部署版本、运行时地址 |
| 可视化Demo页面 | 本地页面、Live 参数任务链路、只读权限预览和脱敏 TXT/CSV 提交前核对完成；在线部署待做 | 在线地址与三分钟演示视频 |
| Agent设计与工具编排 | 最新版只读 MCP 已完成 ARM64 容器内协议验证；云端未验证 | AgentArts 工具卡片与云端调用链 |
| 知识接入 | 待设计 | 安全规则知识库及引用证据 |
| 多Agent协作 | 本地三角色证据契约与离线模拟已完成，真实协作未验证 | 三Agent运行Trace |
| 效果评估 | 待成员C实现 | 评测集、基线对比、AgentArts评估报告 |
| 初赛材料可复现 | 60 项后端测试、28 项前端测试及构建通过；最新只读 MCP ARM64 容器协议验证通过 | AgentArts 云端调用录像与演示视频 |

## 先上传材料再领取赛事资源

赛题 1、赛题 2 参赛队员的资源通知要求：队伍完成报名组队、至少一名队员按官方 Word 模板上传一次有效初赛材料、队员本人完成华为云实名认证，之后才进入每周白名单核验。2026 年 12 月 9 日 17:00 是代金券资格的最后一次名单导出。首次上传不要求完整作品或 Demo 链接；可继续修改，初赛评分以作品截止前最后一次提交为准。每位符合条件的队员独立领取 350 积分，经开发者成长中心兑换代金券；积分并非等值现金，也不能假设不同账号可以合并使用。

曾根据本机下载的**赛题 2 Word 模板**生成项目内容草稿；2026 年 11 月 10 日检查时，原 `outputs` 路径已无该 Word 文件。请队长以自己持有的最新版为准，核对队伍实名信息、联系方式和团队合照后上传；若文件丢失，可用 [`initial-submission-draft.md`](initial-submission-draft.md) 的内容重建。办理步骤见 [`competition-resource-claim.md`](competition-resource-claim.md)。本地文件不是平台上传回执。

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

- 2026 年 11 月 11 日复建并加载当前代码的 `linux/arm64` MCP 镜像，在本机回环端口运行容器；`/ping` 返回 `ok`；
- 2026 年 11 月 10 日以锁定的 `mcp==1.28.1` 复验最新服务：MCP `initialize` 协商成功，协议版本为 `2025-03-26`；
- 最新 `tools/list` 只返回 `preview_activity`、`runtime_status`，不包含审批或执行工具；
- 最新 `tools/call` 已成功调用两工具；预览返回 `PREVIEW_ONLY`，40 人样例三步决策为 `ALLOW / CONFIRM / CONFIRM`；
- 端到端校园活动样例在完成低风险步骤后停在`WAITING_CONFIRMATION`，未直接执行文件更新和群发通知。
- 任务护照授权不可重放，普通HTTP API不暴露绕过护照的原始工具入口。
- 前端 Live 模式可提交结构化活动参数并展示规划证据与护照；默认规划器仍是本地离线适配器。
- 2026 年 11 月 10 日新增权限预览、脱敏 TXT/CSV 来源检查和只读人数核对后：后端 60 项、前端 28 项测试和前端生产构建通过。来源检查只保留摘要，不执行资料中的指令；人数核对不自动授权，也不证明已完成通用提示注入识别。

## 暂不能宣称完成的能力

- 尚未在AgentArts控制台创建和部署真实多智能体；
- 尚未完成AgentArts平台评估；
- 最新 MCP 服务已完成 ARM64 容器内协议验证；尚未完成华为云 SWR 和 AgentArts 运行时上的 `tools/list/tools/call` 验证；
- 2026 年 11 月 11 日，Chrome 跳转华为云登录页时返回 `ERR_CONNECTION_CLOSED`；未登入 AgentArts，也未启用任何可能计费的云服务；
- 当前模拟工具不等同于真实学校、社区或企业系统接入。
- 演示 HTTP API 尚无身份认证，不得作为公网可写服务部署；AgentArts 只能访问只读预览 MCP。
- 详细策划案对照见 [`project-plan-review.md`](project-plan-review.md)：真实资料的有用处理、独立评测集和用户访谈尚未完成。

## 比赛要求复核依据

- [华为ICT大赛创新赛中国区官方赛题入口](https://e.huawei.com/cn/talent/#/ict/innovation-details?zoneCode=027425&zoneId=98269700&compId=85132021&divisionName=%E4%B8%AD%E5%9B%BD%E5%8C%BA&type=C002)
- [赛事资源积分领取入口](https://gallery.developer.huaweicloud.com/gallery/competition?type=innovation)
- [初赛作品上传操作指导](https://e.huawei.com/cn/talent/news/#/details?consultationId=5970)
- [大连理工大学2026—2027华为ICT大赛通知](https://chuangxin.dlut.edu.cn/info/1020/16867.htm)
- [AgentArts MCP Server镜像开发说明](https://support.huaweicloud.com/highcode-agentarts/agentarts_10_080.html)
- [AgentArts MCP Server运行时部署说明](https://support.huaweicloud.com/highcode-agentarts/agentarts_10_127.html)
