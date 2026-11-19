# Five main presentation figures

最新图目录：`github_upload/outputs/final_acceptance_20261118/figures/`。全部使用最终兼容环境数据；距离mm，控制步20ms。

已执行生成命令（仓库根目录）：

```powershell
& .\.venv\Scripts\python.exe github_upload/final_acceptance.py
& .\.venv\Scripts\python.exe github_upload/prepare_presentation.py
```

这两条读取已有原始运行，不训练或搜索参数。当前产物已存在；作图脚本拒绝重复创建图目录。需重建时在新副本调整OUT常量，保留验收产物。普通演示无需重跑它们。

| 图 | 单位及数据来源 | Slide结论 | 必须说明的限制 |
|---|---|---|---|
| 01_trajectory.png | 真距离mm、状态步；compatible探索test/traces → selected_traces.json | The predeclared example shows weak visible differences, which we retain. | 策略1/seed930000/.10rad bias/start70；按首策略首状态、最大预声明幅值、最晚时段选取，不按效果筛选；一个案例不能证明鲁棒性 |
| 02_timing.png | 窗口配对增量mm、最终十步均距mm、start步；compatible test CSV与清洁轨迹 → verified_episodes.csv | Later bias slightly increases final error, but no unprotected short attack causes task failure. | 每点90状态，不同点复用状态；仅无防御曲线；时机比较不能证明观测通道依赖的因果机制 |
| 03_alarm_background.png | 窗口比例/90；compatible逐步报警 → paired_windows.csv、window_rates.csv | Attack windows alarm more often than matched normal windows; an alarm is not attribution. | 正常13/90或17/90，攻击76/90–90/90；短攻击检测观测窗全完整，中止观测已处理但动作未执行。持续攻击另表记录各73个截断检测窗；延迟仅在曾报警者计算 |
| 04_defense_cost.png | 中止数、每回合修正数、完整轨迹角度MAE(rad)；compatible原始CSV与日志 → presentation_cohorts.csv | Wait+1 avoids four short-condition aborts but delays sustained response by20ms. | 每方法正常90、短条件1080、持续90；条件不是独立状态；完整轨迹代价有幸存者选择，必须连同中止数；无防御本已全部成功 |
| 05_abort_case.png | 残差mm、报警数、步；compatible main/traces → selected_traces.json | A post-attack noise alarm extends20 attack alarms to21 and triggers a rule-induced abort. | 已知历史策略3/802009；不是平均效果；真距离约3.849mm只用于评分；random_bias重复同一状态，不是第二个独立状态 |

各图清晰英文标题已写入PNG。完整条件表在verified_episodes.csv；截断暴露在paired_windows.csv。原始日志保留SI米字段用于审计，展示统一mm。架构复用根目录proposal_reference_exact_diagram.png，来源为已有小组素材。
