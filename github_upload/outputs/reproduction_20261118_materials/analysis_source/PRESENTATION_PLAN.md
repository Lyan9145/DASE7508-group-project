# 五人、12 分钟展示提纲

正文每人 2分16秒，四次换人各10秒，共12分钟。以下 A–E 是待小组确认的讲述分工，不代表实际作者贡献。所有数字由 FINAL_RESULTS.md 与其证据表填写，不将历史数据称作本机新测。

| 页 | 讲述/时间 | 核心信息 | 真实图表与证据 |
|---|---|---|---|
| 1 | A / 0:00–1:08 | 问题与信任边界：仅 joint0 cos/sin 欺骗，位置和速度受保护，真值只评分 | github_upload/security.py、reacher_env.py，PROTOCOL.md；用代码通道索引0/2说明 |
| 2 | A / 1:08–2:16 | 三个冻结策略、配对噪声、100步与最后10步成功判据；90个状态不是4500个独立样本 | main_plan.json；materials/reproduction_totals.csv；环境版本取 environment.json |
| 换人 | 2:16–2:26 | A→B | 10秒 |
| 3 | B / 2:26–3:34 | 历史审计与本机复现，分别列数值差异和计时；历史2250/2250对2248/2250 | materials/reproduction_comparison.csv、reproduction_totals.csv；environment/historical_audit.json、local_audit.json |
| 4 | B / 3:34–4:42 | 防御为何造成失败：20步攻击报警后，噪声带来第21次，真距离已很小 | materials/abort_case.png、abort_step_log.csv；failure_diagnostic/episodes.csv；必须展示失败记录 |
| 换人 | 4:42–4:52 | B→C | 10秒 |
| 5 | C / 4:52–6:00 | 新独立时机实验：20/50/70开始，20步，.05/.10rad，bias/ramp；保持零效果结果 | materials/timing.png、per_policy_results.csv；exploratory_20261118/test/config.json |
| 6 | C / 6:00–7:08 | 代表轨迹与终点恢复；首策略首测试seed930000、最大预声明bias、最晚时段，不按效果选图 | materials/representative_trajectory.png；test/traces.jsonl.gz；最终距离只看完整100步，截断标注 |
| 换人 | 7:08–7:18 | C→D | 10秒 |
| 7 | D / 7:18–8:26 | 报警不等于识别攻击：逐步、窗口、整回合概率不同，比较配对背景增量 | materials/alarm_background.png、window_alarm_summary.csv、new_clean_false_alarms.csv；历史1.02%与63/90独立说明 |
| 8 | D / 8:26–9:34 | 恢复等待规则：第21次进入pending，正常则恢复，持续异常第22次中止；开发集平局选最短等待 | recovery_monitor.py；exploratory_20261118/preregistered_plan.json、frozen_selection.json；两候选开发均15次中止，不使用测试调参 |
| 换人 | 9:34–9:44 | D→E | 10秒 |
| 9 | E / 9:44–10:52 | 短攻击无/原/改进成功1080/1076/1080（各1080条件）；持续攻击原/改进均73/90中止，改进晚20ms；改善有范围和代价 | materials/defense_cost.png、cohort_comparison.csv、alarm_prediction_summary.csv、sustained_response_pairs.csv；持续40步的sustained行必须单列 |
| 10 | E / 10:52–12:00 | 结论以实测为准；旧案例修复不等于广泛收益，3策略限制，时机不能证明观测通道因果 | FINAL_RESULTS.md；可演示正常/攻击/防御各一小段预录视频；保留零效果、误报和失败，最后留复现入口 |

上表中的 `materials/` 指 `github_upload/outputs/reproduction_20261118_materials/`；`environment/` 指 `outputs/reproduction_20261118_environment/`；`failure_diagnostic/` 指 `outputs/reproduction_20261118_failure_diagnostic/`。

展示前核对：按策略表检查汇总是否掩盖不同策略；终点成功与瞬态偏移分开；所有距离图用mm，延迟报告step与20ms/step。窗口报警的区间是策略内配对初始状态bootstrap，不是对时间步或重复条件独立重采样。持续异常中止的低动作平方和是截断结果，不称机械能节省。主图不使用大热力图。

可能问题与回答依据：

- 为什么攻击没有使任务失败？在规定小幅、短时攻击下，瞬态偏移和最终成功可以同时存在；较早攻击留有恢复时间，策略也观察受保护的末端位置。时机实验仅比较时段，不能证明通道依赖的因果机制。引用 timing.png 与对应成功计数。
- 99%阈值为何70%正常回合报警？99%是逐步分位数；99个机会下至少一次报警概率可较高。历史实测逐步约1.02%，63/90整回合至少一次，不能混用分母。
- 攻击窗口检测率很高就表示准确检测吗？不能。展示相同正常窗口的报警率、配对增量、无报警比例、条件延迟和区间，说明噪声贡献。
- 是否通过测试集调参？没有。开发seed910000块，测试930000块；选择文件在测试前保存。候选仅1/3步等待，开发中止相同，按预定平局规则选1步。
- 改进是否取消中止？没有。原规则第21次，改进第22次连续报警中止。展示40步持续攻击响应；这是约20ms额外反应时间的明确代价，不宣称无代价。
- 改进能否保证真实机器人安全？不能。只有三个策略，同一仿真几何，且速度/位置受保护。旧失败案例能完成只能作为诊断证据，新测试的真实差异见表。
- 为什么不同机器数值不同？Python/Torch与平台不同；模型哈希相同，源码与日志已保存；成功变化和最大数值差异用 reproduction_comparison.csv回答，计时单列。

实际贡献须由小组填写后确认：

| 成员真实姓名 | 实际完成工作 | 可核对提交/文件/实验记录 | 全组确认 |
|---|---|---|---|
| 待确认1 | 待填写 | 待填写 | 待确认 |
| 待确认2 | 待填写 | 待填写 | 待确认 |
| 待确认3 | 待填写 | 待填写 | 待确认 |
| 待确认4 | 待填写 | 待填写 | 待确认 |
| 待确认5 | 待填写 | 待填写 | 待确认 |

AI使用说明草稿（按课程要求由小组确认）：使用Codex协助阅读既有代码、配置Windows/mp1本地复现环境、实现独立探索入口及恢复确认候选、运行测试和模拟、核算结果、制作图表与报告草稿。既有模型未重训、历史结果未覆盖、失败及零效果未删去。小组应核验原始日志、理解信任边界、复查统计和引用，并对最终提交及真实成员贡献负责。AI不应被列作小组成员，草稿不替代课程规定的使用披露格式。
