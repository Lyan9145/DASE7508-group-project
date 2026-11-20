# Fixed paired demo and recording guide

已实际完成：四模式固定边界案例的数值运行、MuJoCo RGB渲染、GIF生成、HTML文件生成和step40截图检查。第二组预声明首状态已完成四模式数值检查。**未生成桌面录屏MP4，未验证人在场的浏览器播放/投影效果。** GIF是生成的慢速模拟器回放，不是实录桌面；课程允许annotated trace作为代表运行。

先在仓库根目录打开现成回放（无需重跑）：

```powershell
Invoke-Item .\github_upload\outputs\final_acceptance_20261118\demo_boundary_v2\replay.html
# 静态备份
Invoke-Item .\github_upload\outputs\final_acceptance_20261118\demo_boundary_v2\boundary_step40.png
```

固定配置：policy3/model，seed802009，noise_seed10802009，bias−0.10rad，观测窗[20,40)，dt20ms；读取compatible_main的policy3校准阈值，wait=1。四模式共享初始状态、噪声和攻击日程，正常模式只取消注入。原规则40动作后在观测40中止；其余三种完成100动作。本例已知历史失败，**不是平均效果**，总体结果见图04。

真距离仅用于显示与任务评分，先把数值轨迹固定，再用独立render环境重放；模型只接收policy_obs，monitor只接收reported。界面显示模式、模拟时间/步、攻击窗/注入量、真距离mm、报警/连续数、中止；中止画面冻结并标识，不伪装成后续动作。GIF按每两步取一帧，慢放，时间标签仍是模拟时间。

重新生成四模式带显示的demo（仓库根目录；每次全新目录）：

```powershell
$py = (Resolve-Path .\.venv\Scripts\python.exe).Path
$run = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
& $py github_upload/presentation_demo.py --scenario boundary --mode all --out "github_upload/outputs/demo_boundary_$run" --open
```

分别运行四种固定模式（会保存各自的回放和CSV）：

```powershell
& $py github_upload/presentation_demo.py --scenario boundary --mode normal --out "github_upload/outputs/demo_normal_$run"
& $py github_upload/presentation_demo.py --scenario boundary --mode attack --out "github_upload/outputs/demo_attack_$run"
& $py github_upload/presentation_demo.py --scenario boundary --mode original --out "github_upload/outputs/demo_original_$run"
& $py github_upload/presentation_demo.py --scenario boundary --mode improved --out "github_upload/outputs/demo_improved_$run"
```

模型1首个探索状态/较晚窗口的弱效果示例（不按效果选择）：

```powershell
& $py github_upload/presentation_demo.py --scenario representative --out "github_upload/outputs/demo_representative_$run"
```

只做最短数值检查，不创建渲染器/窗口：

```powershell
& $py github_upload/presentation_demo.py --scenario boundary --numeric-only --out "github_upload/outputs/demo_numeric_$run"
```

现有demo.py命令仍可用，提供原来的human窗口；没有状态叠层，不能替代本轮注释对照。希望看动作时可运行`& $py github_upload/demo.py --attack clean --episodes 1`。不必重新训练，不需要CUDA或EGL。

## 约70秒录屏/讲解脚本（包含在E的75秒内）

| 时间 | 画面/操作 | 英文讲解重点及证明范围 |
|---|---|---|
| 0–10s | 显示四面板配置标题 | “This is a selected historical boundary case, not the average result.” 固定模型/seed/噪声，避免观众误认为随机典型效果 |
| 10–25s | 重播GIF，指四种模式和攻击窗 | “Only the angle observation is corrupted. The physical state is not directly changed.” 物理动作看起来相近是允许结果 |
| 25–45s | 切静态boundary_step40.png，可缩放 | “At step40, the original rule aborts at alarm21; wait+1 continues. True distance is display-only.” 同一时刻看中止边界，不能说检测更准确 |
| 45–60s | 回GIF看冻结面板与完成CSV | “Normal and unprotected attack also finish. The original aborted panel is frozen.” 展示副作用，而非优于无防御 |
| 60–70s | 切图04/末页统计 | “Across held-out states, four short-case aborts are avoided, with a20ms sustained-response cost.” 案例与总体区分 |

人工录屏：先打开本地HTML并检查GIF循环、字体和四模式显示；用Windows可用的录屏工具录制上述70秒，保持“selected case”和“display only”标签；播放一次检查声音、大小与实际总时长。工具不可用时课程允许直接用annotated trace或静态截图备份。保存文件时注明screen recording或simulator replay，不能把本轮GIF称为已完成MP4录屏。

失败回退：HTML关联失败→浏览器打开本地replay.html；GIF不播放→用step40静态图+episodes.csv；渲染失败→使用已生成的回放，数值检查仍可运行。现场不改阈值、幅值或seed。
