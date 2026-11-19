# 本机独立复现报告（2026-11-18）

最终交付环境：mp1 Python 3.12.14作为基础，项目本地.venv内Torch 2.14.1+cpu。依赖检查无冲突，16项测试通过，数值与Windows离屏渲染均通过。最终完整运行位于 github_upload/outputs/reproduction_20261118_compatible_main 和 exploratory_20261118_compatible；两轮完整日志审计均通过。成功判定与历史一致；正式最终十步均距最大差约0.000027mm。下文保留初次mp1旧Torch排查，最终补验与差异在文末。

Windows ZIP 项目无 .git，不能独立证明分支名；代码、模型、main_v1、pilot 与方案均存在。未发现适用 AGENTS.md。三个模型哈希与历史配置核对：{'sac_seed_1_sync': True, 'sac_seed_2_sync': True, 'sac_seed_3_sync': True}。

使用 mp1 Python 创建本地 .venv，复用 mp1 Torch；没有重新训练。环境：{"python": "3.12.14 | packaged by Anaconda, Inc. | (main, Aug 27 2026, 14:37:13) [MSC v.1942 64 bit (AMD64)]", "executable": "C:\\Users\\76803\\Desktop\\course\\7508\\DASE7508-group-project-codex-sensor-spoofing-pilot\\.venv\\Scripts\\python.exe", "base_prefix": "C:\\anaconda\\envs\\mp1", "platform": "Windows-11-10.0.26200-SP0", "cpu": "Intel64 Family 6 Model 170 Stepping 4, GenuineIntel", "logical_cpus": 22, "packages": {"torch": "2.7.1+cu126", "numpy": "2.4.6", "mujoco": "3.15.0", "gymnasium": "1.4.0", "stable-baselines3": "2.9.0", "pytest": "9.1.1", "matplotlib": "3.11.2", "pandas": "3.0.6"}}。

原锁联网 dry-run 成功。受限网络、uv 默认缓存与 ensurepip、pytest 临时目录曾失败，日志在 outputs/reproduction_20261118_environment。改用本地 uv 缓存安装原锁除 Torch 外的包；Torch 使用 mp1 2.7.1+cu126，所有评估 CPU。原锁未改写。本机核心版本见 environment-windows-mp1.lock.txt，完整依赖见环境目录 pip_freeze.txt。16 项测试通过（tests_final.log），数值与 Windows GLFW 离屏渲染分别通过；未设置 EGL。

历史与本机回合核算：

| dataset | defense | successes | episodes | aborts |
|---|---|---|---|---|
| historical | False | 2250 | 2250 | 0 |
| historical | True | 2248 | 2250 | 2 |
| local | False | 2250 | 2250 | 0 |
| local | True | 2248 | 2250 | 2 |

逐项比较：

| metric | unequal | max_abs_difference |
|---|---|---|
| task_success | 0 | 0.0 |
| aborted | 0 | 0.0 |
| steps | 0 | 0.0 |
| alarm_count | 0 | 0.0 |
| final_10_mean_distance_m | 97 | 1.0061396160665481e-16 |
| terminal_distance_m | 140 | 1.0061396160665481e-16 |
| window_mean_distance_m | 72 | 1.0061396160665481e-16 |
| control_effort | 0 | 0.0 |

历史正常逐步报警率 1.021324%，整回合 63/90。失败记录见 local_failures.csv；seed 802009 的 bias/random_bias 均在 40 步、连续第21次报警中止。bias 中止时残差 6.9769 mm，真距离 3.8490 mm。完整日志见 abort_step_log.csv。

历史运行 126.90 s，本机 290.16 s（包含校准；本次与审计/探索并发，计时不可视为硬件基准）。历史审计另存 historical_audit.json，本机审计另存 local_audit.json。源码快照按历史 manifest 校验；当前 evaluate 仅新增可选 monitor_factory，正式默认规则保持不变，check_setup/audit 的输出防覆盖另作修改。

精确命令见 README.md 与 outputs/reproduction_20261118_environment/commands.ps1。渲染数值检查均成功；human 窗口交互未自动验证。本机并非历史 Python/Torch 二进制环境，因此有数值差异须以 reproduction_comparison.csv 为准。

硬件：Intel Core Ultra 7 155H，16核22线程；hardware.json保存实际查询。探索开发1008回合，独立测试3780回合，另有600回合探索校准；正式复现4500+300校准，小规模20+100校准。历史summary.csv的每组回合数、成功数与平均最终距离均从episodes.csv重新核对通过。


兼容性最终补验：第一次 mp1 Torch2.7.1 下虽然数值与测试通过，最终 pip check 发现 SB3 2.9.0 声明需要 Torch>=2.8。该问题已修复：仅在项目.venv安装原锁 Torch2.14.1+cpu，mp1本身未修改。pip_check_compatible.log 为 No broken requirements found；tests_compatible.log 16项通过。完整4500回合与开发1008/测试3780回合均在兼容环境重新运行，分别保存 reproduction_20261118_compatible_main 和 exploratory_20261118_compatible。成功、中止、步数、报警数及窗口报警时间逐条一致，但浮点轨迹不逐位一致。正式最终十步均距最大差0.000026805mm，终点距离最大差0.000035683mm，动作平方和最大差约1.77e-7；探索最大配对窗口增量差0.000009602mm。详见 compatible_environment_comparison.csv及supported_vs_history.csv。最初逐值检查的1e-10门槛未通过（保留compatible_verification.log初次失败另存副本），已定位实际差异并如实报告，不称为精确数值复现。后者为相同seed重复复现，不增加独立样本数。兼容正式复现用时 286.37s；最初290.16s属于旧Torch兼容性探查记录。

最终可用依赖为 environment-windows-mp1.lock.txt（CPU索引），旧环境版本仍保存在environment.json与初次config；当前环境另见compatible_environment.json。主图和表使用首次数值数据，已由兼容重跑逐项核对，不将两轮重复条件合并。

改进状态的数学含义就是将连续中止边界从第21次改到第22次；pending不提供额外观测证据，不表示已经确认恢复。若噪声连续更多步，仍可误中止。报警时预测角度误差先按回合聚合：短bias约0.02555rad、短ramp约0.03594rad，正常误报警约0.00110rad；均不可与全回合角度MAE混为同一量。见prediction_cohort_summary.csv，截断仍需单列。开发选择在兼容重跑中也完全一致。

证据入口：[结果索引](github_upload/outputs/reproduction_20261118_materials/READ_ME_FIRST.md)、[兼容正式日志审计](github_upload/outputs/reproduction_20261118_environment/compatible_main_audit.json)、[兼容探索日志审计](github_upload/outputs/reproduction_20261118_compatible_audit/exploratory_audit.json)。

以每个初始状态在全部12种短攻击下是否均成功为单位：原防御86/90，改进90/90，配对增量4/90，固定三个策略内bootstrap95%区间 0.0111–0.0889。这是本组预声明条件整体通过率，不代表单个新攻击条件或新策略总体收益。


本轮最终证据验收：完整兼容运行已再次逐步核验，结论计数不变；最新证据见FINAL_ACCEPTANCE.md和github_upload/outputs/final_acceptance_20261118/READ_ME_FIRST.md。presentation五张图现全部重新从兼容运行生成，旧图保留。新正常逐步误报89/8910、整回合54/90，勿与历史91/8910及63/90混用。窗口完整性说明已纠正：短攻击检测观测窗全部完整（中止观测已检测）；3个攻击动作窗及4个攻击动作加后10步距离窗不完整。持续攻击各73个检测窗截断，缺失后缀不当正常。旧complete_windows以完成动作数判断，不能用来表示报警观测暴露；最新paired_windows.csv以实际观察数判断。改进仅避免规则中止，不优于已全成功的无防御；一步等待不增强攻击归因或结束检测。
