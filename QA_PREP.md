# Q&A preparation / 约3分钟现场问答

回答先给一句结论，再指证据；不要把整份备份表念完。下面12题对应课程反思要求。

1. **Why did the unprotected arm always succeed? / 为什么无防御全成功？**
   EN: Within the tested small, short attacks, perturbations change transient errors but not final success. Earlier attacks leave recovery time. Protected position input may also help, but we did not establish that causal explanation through ablation.
   中：1080/1080只是当前条件；恢复时间有时序依据，位置帮助属于合理解释而非已证实因果。证据：图02、short_totals.csv。

2. **What is the security value if attacks do not cause failure? / 安全研究价值？**
   EN: We quantify a threat boundary and a mitigation trade-off. The original defense introduces four short-condition aborts that the unprotected baseline does not have. A bounded wait avoids them but delays sustained response by20ms. Negative attack results prevent unsupported vulnerability claims.
   中：安全控制本身也有可用性代价；报告无效攻击符合课程要求。证据：cohorts、sustained_pairs。

3. **What can the attacker change? / 能改哪些通道？**
   EN: Only joint0's cosine and sine, observation entries0 and2, with a bounded bias or ramp in one declared window. It cannot change target, joint1, velocity, position, dynamics, reward, policy weights or monitor code.
   中：假设已取得该传感器访问，不演示入侵。证据：security.py/Attack；逐步保护通道审计。

4. **Why trust independent position and velocity? / 可信依据？**
   EN: It is an explicit simulator threat-model assumption. The wrapper produces separate channels before angle-only injection, and logs verify they are not modified. This does not prove independence or resistance to compromise on physical hardware.
   中：代码验证未被本攻击修改，不等于现实不可被攻击。证据：reacher_env.py、FINAL_ACCEPTANCE。

5. **What are the detector's blind spots? / 检测盲区？**
   EN: Small offsets and folded poses can create residuals below the noise-calibrated threshold. Gradual attacks can be accepted before an alarm and bias the predictor's starting angle. Noise itself can alarm, and long prediction chains can drift.
   中：不能将高窗口报警率叫准确识别。证据：window_rates.csv、原ANALYSIS_NOTES、prediction日志。

6. **Why is waiting not better detection? / 一步等待为何不增强检测？**
   EN: The residual, threshold and correction are unchanged. We only shift the abort boundary from21 to22 consecutive alarms. The extra state provides no new evidence that an attack has ended.
   中：是时间容忍度变化，不是更准确分类。证据：recovery_monitor.py与已执行源码快照。

7. **What does the20ms delay cost? / 20ms代价？**
   EN: In all73 shared sustained-attack aborts, intervention termination occurs one action later. More anomalous operation is allowed before stopping. We have not measured physical safety risk; this is an experimental abort, not a certified safety stop.
   中：不能因为20ms短就说无害。证据：sustained_pairs.csv，dt=.02秒。

8. **How did you prevent test-set tuning? / 如何防止测试调参？**
   EN: Calibration states set thresholds; separate development states compare only the predeclared1/3-step waits. Both have15 aborts and the fixed tie-break selects1. The execution code saves the selection before running test states. Local files support this sequence but do not provide external timestamp certification.
   中：开发910000块、测试930000块、校准900000块。原始本地记录不是外部预注册。证据：seed_inventory、frozen_selection、source/exploration.py。

9. **Are1080 trials independent? Why only three policies? / 独立性和三个策略限制？**
   EN: No. They are12 conditions repeated on90 paired states from three training policies. The four avoided aborts involve four different states, but only two policies. State-level paired analyses condition on these three policies and cannot establish broad cross-policy generalisation.
   中：4状态不是4独立训练重复；不要用条件数量夸大样本。证据：four_failures.csv及主配置。

10. **Could the lower error/cost be caused by early aborts? / 截断是否让指标虚低？**
    EN: Yes, if naively pooled. We count every abort as task failure, mark incomplete windows, and report complete100-step final distances separately with abort counts. Complete-only means still have survivor selection, so they do not prove efficiency gains. Action squares are not mechanical energy.
    中：持续73/90截断尤其要单列。证据：verified_episodes.csv、图04、FINAL_ACCEPTANCE。

11. **Does a high window alarm rate mean accurate attack recognition? / 窗口报警等于准确识别？**
    EN: No. Matched normal20-step windows alarm in13/90 or17/90 cases. Attack windows have76/90 to90/90 observed alarms. We report the paired increment, conditional first-alarm delay and no-alarm proportion. Truncated windows retain their observed exposure; unseen samples are not treated as clean.
    中：新正常逐步89/8910，整回合54/90，与窗口分母不同。证据：false_alarms.csv、window_rates.csv、paired_windows.csv。

12. **What is reused, what is new, and what remains unfinished? / 原有与新增？**
    EN: We reuse MuJoCo, Gymnasium, SAC/SB3 and the existing group models, attacks, monitor and main study. Later work adds Windows reproduction, the held-out timing study, bounded waiting, audits and evidence materials. This acceptance round adds trace rechecks, annotated replay and presentation drafts. Actual member authorship requires group confirmation. A second-computer check, timed rehearsal and final submission remain pending.
    中：不按A–E讲者自动分成果；AI协助须披露。证据：TEAM_HANDOFF、PRESENTATION_PLAN、源码快照。

备选追问：下一步不应盲目增大攻击。可预声明更多训练策略与按姿态分层测试，同时衡量误中止、响应延迟和预测漂移；真实多通道可信性需要独立硬件或系统验证，不能从现有仿真推断。
