# Slide-ready content:10 main slides + backups

Figure prefix:github_upload/outputs/final_acceptance_20261118/figures/。总正文660秒；换人40秒+缓冲20秒。英文可直接放PPT，中文用于理解。真实姓名/贡献待小组确认。

## 1 — When Can a Sensor Monitor Make Reaching Worse?
A ·66s

- Joint-angle spoofing in a SAC-controlled simulated arm.
- Question: does kinematic mitigation improve reaching under bounded corruption?
- Measure transient errors, task completion, false alarms and false stops.
- Team names and IDs: confirm before submission.

Visual:01_trajectory.png small crop。中文：资产是传感器完整性与任务完成，攻击目标是用错误观测影响动作。不要先承诺攻击能制造任务失败。

## 2 — System and Trust Boundaries
A ·66s

- MuJoCo/Reacher-v5; frozen SAC policies;100-step episodes.
- Attacker changes only joint0 cosine/sine entries0 and2.
- Target, joint1, position and velocity remain protected by assumption.
- Simulator truth is evaluation/display only.

Visual:proposal_reference_exact_diagram.png。Flow:sensors→angle injection→optional monitor→policy→simulator；truth→evaluator独立箭头。中文：初始入侵不在研究范围；位置速度独立可信是假设，仍有2mm位置噪声，并非已验证的硬件隔离。

## 3 — Attacks and What We Added
B ·66s

- Bias: fixed signed offset; ramp: offset grows within the window.
- Matched random-sign controls preserve the magnitude envelope.
- Existing: trained policies, attacks, original monitor and frozen main study.
- Added: Windows reproduction, held-out timing study, wait rule and audits.

Visual:security.py/Attack.delta的日程定义或简洁公式。中文：原正式实验包含全部12设置及随机对照；本次不声称发明SAC或运动学方法，实际成员贡献需证据确认。

## 4 — Timing Changes Errors, Not Observed Task Success
B ·66s

- Bias/ramp;ε=0.05/0.10rad; duration20; starts20/50/70.
- Three frozen policies;30 new paired states per policy.
- At0.10rad bias, final error:5.581→6.157mm (start20→70).
- All1,080/1,080 unprotected short-attack conditions succeed.

Visual:02_timing.png；01_trajectory.png为备份案例。中文：最终误差略增仍小于30mm阈值，窗口增量并非随时机单调增大；不能证明观测通道依赖的因果关系。首状态弱效果例子未按效果选择。

## 5 — Kinematic Consistency Is an Anomaly Signal
C ·66s

- Residual=‖forward kinematics(reported angles)−measured position‖.
- Threshold:99th percentile from100 clean calibration episodes per policy.
- Alarm correction: previous angle + previous trusted velocity×20ms.
- Noise, folded geometry and gradual offsets create blind spots.

Visual:架构图可信箭头+残差公式，图03留给D展开。中文：原始观测决定报警；初始读数初始化。残差超阈值不等于攻击归因，低于阈值的渐变角度还可能污染预测起点。

## 6 — One Extra Step Changes the Abort Boundary
C ·66s

- Original: abort on21 consecutive alarms.
- Wait+1: pending on21; clear reading resets; alarm22 aborts.
- Same detector/predictor; no additional trusted channel.
- Development1/3-step candidates tie at15 aborts; fixed tie-break selects1.

Visual:05_abort_case.png。中文：原历史例子攻击20次报警后由噪声延伸为21；等待仅把边界延后，不是更准确检测恢复。状态normal→correcting→pending→abort，任一清洁读数回normal。旧案例回放不当新独立测试。

## 7 — Paired Evidence, Not Thousands of Independent States
D ·66s

- Three policies×30 paired states=90 state units.
- Main reproduction:2250/2250 without defense;2248/2250 with original defense.
- Success:100 actions, no abort, final10-state mean distance≤30mm.
- Disjoint data splits; matched initial states, sensor noise and attack schedules.

Visual:三行计数小表；源compatible_main/episodes.csv与acceptance.json。中文：4500是重复条件。历史两失败同一状态在bias/random_bias重复。阈值可由开发与测试共用，但校准状态不能混入评价。

## 8 — Fewer False Stops, With a Response Trade-off
D ·66s

- Short successes:1080/1080,1076/1080,1080/1080 (none/original/wait+1).
- Four avoided aborts:four distinct state units, two policies.
- Sustained:both defenses abort73/90; wait+1 responds20ms later.
- Clean:89/8910 step alarms;54/90 episodes alarm.

Visual:04_defense_cost.png主图；03_alarm_background.png用第二视觉build或备份。中文：无防御本已全成功，不能称优化优于无防御。正常窗口13/90或17/90，攻击76/90–90/90；报警不等于准确识别。图中完整轨迹代价有幸存者选择，中止始终计失败。

## 9 — Selected Boundary Case:Four Paired Modes
E ·75s，含demo

- Same policy3, seed802009, noise stream and20-step bias window.
- Normal / attack / original / wait+1 shown together.
- At step40, original aborts at streak21; wait+1 continues.
- Selected case, not average performance; truth is display-only.

Visual:outputs/final_acceptance_20261118/demo_boundary_v2/replay.html或comparison.gif；静态boundary_step40.png备用。中文：按DEMO_GUIDE约70秒脚本；这是慢速MuJoCo注释回放，不是桌面录屏。故障就用静态截图，不现场安装修环境。

## 10 — Takeaways, Limits and Next Tests
E ·57s

- No observed task-failing unprotected attack in the tested scope.
- Consistency checks can reduce transient error yet introduce false stops.
- Wait+1 reduces boundary aborts, not attack-identification errors.
- Future:predeclare more policy seeds and pose-stratified tests; measure false stops, delay and prediction drift.
- Credit reused tools/group code; confirm member contributions; disclose AI help.

Visual:三条takeaways与credits细条。中文：仅当前仿真、幅值和可信通道；不证明普遍鲁棒性。未来工作只提案，本轮不执行、不增幅寻找成功案例。

## Backup B1 — Full Conditions and Per-Policy Results

真实完整条件表：final_acceptance_20261118/verified_episodes.csv；各策略原始结果：exploratory_20261118_compatible/test/episodes.csv；四失败：four_failures.csv。按问题筛选对应条件展示，主文不用密集热力图。保存所有零效果和失败。

## Backup B2 — Denominators and Censoring

Step false alarm=clean alarms/(90×99)；episode rate=episodes with alarm/90；window rate=windows with observed alarm/90 per condition，另列截断/暴露。延迟仅曾报警者；无报警另列。中止计失败，完整距离均值排除截断但有幸存者选择。动作平方和不是机械能。无防御检测率为N/A。

## Backup B3 — Credits and References

成员真实贡献须全组确认，拟分工不是实际贡献证据。复用MuJoCo、Gymnasium Reacher、SB3/SAC；原参考文献在DASE7508_Proposal_2.0.md（Haarnoja、Raffin、Huang及Farama文档）。架构图为已有项目素材。Codex协助实现、复现、分析、验收与讲稿草拟；人需核验并能解释各页。提交日期/格式按Moodle核实。
