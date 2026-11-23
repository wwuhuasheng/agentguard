# 评测工作区

负责人：成员 C（wqy）。

首批数据格式应包含：

- 样本 ID 与类别；
- 用户原始任务；
- 内容来源；
- 预期工具与参数；
- 预期决策（ALLOW / CONFIRM / BLOCK）；
- 预期最终业务状态。

分类目录后续包括 `normal`、`injection`、`privilege`、`parameter` 和 `recovery`。

## 本地 API 回放器

[`local_replay_seed.jsonl`](local_replay_seed.jsonl) 是 8 条虚构烟测，不是成员 C 的独立评测集。每条明确写出预览决策、工具清单、审批序列、任务状态、外部指令信号以及模拟日历、通知、文件副作用的期望值。审批案例覆盖通过、拒绝和两次审批后回滚。运行时每例使用全新的进程内演示 API，不会连接真实工具或发起云端请求：

每条案例必须声明 `provenance`：`SYNTHETIC_DEMO`（虚构演示）、`SYNTHETIC_ATTACK`（虚构攻击）或 `REAL_DEIDENTIFIED`（脱敏真实任务）。后者还必须有 `evidence_ref`，只填非敏感的内部证据编号，指向由组织者私下保管的授权与原始记录；不要把个人资料或证据文件放进仓库。C 同学可按同一 JSONL 格式加入比赛组织过程中的脱敏案例，但需独立人工核对来源和预期结果。`provenance` 是录入者声明，脚本无法证明其真实性；报告只输出来源类别和数量，不输出 `evidence_ref`。当前种子中脱敏真实案例为 **0**。

```bash
PYTHONPATH=. .venv/bin/python scripts/replay_local_eval.py --output .runtime/local-replay-report.json
```

输出 JSON 包含逐例期望与实际不一致的字段、总数、通过数、失败数和各类别分母；接口错误或异常仍记为失败。还记录生成时间、代码提交号、工作区未提交状态、策略及数据集 SHA-256，方便对照运行版本。评测页可在浏览器本地导入 `.runtime/local-replay-report.json`，并与 60 条前端合成样例分开展示；该文件不会上传后端。脚本发现 `AGENTGUARD_PLANNER` 指向云端时直接停止。**8 条烟测通过只表示本地回归正常，不是安全检出率、模型准确率、真实用户效果或 AgentArts 平台评估。**成员 C 可以沿用格式扩充独立标注集，但须另行记录标注者、样本来源、版本、三组基线与人工复核；不要把这 8 条同时当训练样本和盲测样本。

## AgentArts 工作流评估种子

[`agentarts_seed_cases.json`](agentarts_seed_cases.json) 是 8 条**虚构、人工编写的云端分析链路种子**，与成员 C 负责的 20 条端到端人工标注样本分开。它们覆盖正常活动、最小权限、多人通知、外部资料疑似指令、敏感列以及组合风险。`reference_output` 是人工评审要点，尚未由 AgentArts 评估器或真实用户验证，不能当成准确率。

已生成待核对的 [`agentarts_seed_import.jsonl`](agentarts_seed_import.jsonl)，包含与当前工作流开始节点同名的 10 个输入列及 `reference_output`。修改种子后重新导出：

```bash
python3 scripts/export_agentarts_eval_seed.py --output evaluation/agentarts_seed_import.jsonl
```

`query` 是 JSON **字符串**，另有 `reference_signals_json` 字符串；`recipient` 和 `notice_content` 是固定占位值。导出数据不含真实名单、手机号或通知正文。案例 ID 和类别只保存在源文件中，不作为工作流输入列。

华为云[单轮评测集说明](https://support.huaweicloud.com/ops-agentarts/agentarts_14_0027.html)要求先配置列，批量导入可用 JSONL，但要以控制台下载的**当前评测集模板**为准核对列和数据类型。配置 `query`、`title`、`starts_at`、`location`、`recipient`、`notice_content`、`source_trust`、`reference_signals_json` 为 String，`recipient_count` 为 Integer，`update_shared_file` 为 Boolean，`reference_output` 为 String。首次导入宜选择“追加数据”，避免覆盖已有集。

目前工作流尚未发布，用户先前选择跳过附加跨服务授权。华为云[离线评估任务说明](https://support.huaweicloud.com/ops-agentarts/agentarts_14_0086.html)要求发布评测集和工作流，并开启数据上报及 APM/AOM 授权。**这些条件目前未完成，所以尚无 AgentArts 评估分数。**等平台条件具备，再用同一批样本记录每例结果、失败原因、人工复核与版本号；系统失败也计入失败。

