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
| 初赛材料可复现 | 40 项后端测试、25 项前端测试、构建和本地 MCP 协议验证通过 | AgentArts 云端调用录像与演示视频 |

## 初赛材料必须呈现

- 真实需求与目标用户；
- 作品简介和核心创意；
- Agent设计方案与工作流架构；
- 模型、知识库、MCP和其他资产选择；
- 基于AgentArts构建并运行的完整流程；
- 可复现的Demo视频；
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
- 前端 Live 模式可提交结构化活动参数并展示规划证据与护照；目前规划器仍是本地离线适配器。

## 暂不能宣称完成的能力

- 尚未在AgentArts控制台创建和部署真实多智能体；
- 尚未完成AgentArts平台评估；
- 当前MCP服务已完成本地镜像与协议验证，但尚未完成华为云SWR和AgentArts运行时上的`tools/list/tools/call`验证；
- 当前模拟工具不等同于真实学校、社区或企业系统接入。

## 比赛要求复核依据

- [华为ICT大赛官方赛事入口](https://e.huawei.com/cn/talent/#/ict/innovation-details?compId=1234604535111213057&divisionName=practice&divisionId=1234585371000848429&compName=%E5%8D%8E%E4%B8%BAICT%E5%A4%A7%E8%B5%9B2026-2027)
- [大连理工大学2026—2027华为ICT大赛通知](https://chuangxin.dlut.edu.cn/info/1020/16867.htm)
- [AgentArts MCP Server镜像开发说明](https://support.huaweicloud.com/highcode-agentarts/agentarts_10_080.html)
- [AgentArts MCP Server运行时部署说明](https://support.huaweicloud.com/highcode-agentarts/agentarts_10_127.html)
