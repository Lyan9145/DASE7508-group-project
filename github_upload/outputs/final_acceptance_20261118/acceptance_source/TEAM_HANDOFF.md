# Team handoff / 共享运行包

本地共享包：`deliverables/DASE7508_team_handoff_20261118.zip`。只在本地生成，不上传/推送。包内`PACKAGE_MANIFEST.json`记录文件、字节和SHA256；只用明确白名单收集，排除.venv、.uv-cache、pytest缓存、凭据和无关临时文件。

保留：运行/测试源码、兼容依赖锁、main_plan、三个模型与validation、两套冻结校准和配置、主要CSV、五张图、注释回放、讲稿与证据索引。全量traces.jsonl.gz不放包里；完整原始证据仍在原项目github_upload/outputs/reproduction_20261118_compatible_main与exploratory_20261118_compatible，验收前哈希清单保留在final_acceptance_20261118/protected_before.json。包内README说明没有全量日志时不能运行完整逐步验收脚本，不能冒充已再次审计。

## 从解压到运行（Windows PowerShell）

解压到自己可写目录，进入含TEAM_HANDOFF.md和github_upload的根目录。不要进入zip虚拟文件夹直接执行。需要可用的64位Python3.12；本机以mp1为基础，其他成员不要求同名Conda环境。

```powershell
# 先查看可用Python。若没有py，使用自己的Python3.12完整路径替代。
py -0p
py -3.12 -m venv .venv
$py = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $py -m pip install -r github_upload/environment-windows-mp1.lock.txt
& $py -m pip check
```

已有本机mp1并选择以它为基础时，可用以下第一条替代创建环境；不改mp1包：

```powershell
& C:/anaconda/envs/mp1/python.exe -m venv .venv
```

本次交付锁Torch2.14.1+cpu，CPU足够；不设置MUJOCO_GL=egl。首次安装需要网络与下载时间；不保证没装Python的电脑可以完全离线安装。运行包不是依赖wheel离线包。

## 最短数值检查

```powershell
$run = Get-Date -Format 'yyyyMMdd_HHmmss_fff'
& $py github_upload/presentation_demo.py --scenario boundary --numeric-only --out "github_upload/outputs/team_numeric_$run"
```

预期：生成config、episodes、日志和complete状态。四行normal/attack/improved为100动作、成功；original为40动作、中止失败。对照已知案例，不把单案例当总体效果。模型加载和数值仿真不需要图形窗口。

测试与离屏渲染：

```powershell
& $py -m pytest github_upload/test_security.py github_upload/test_exploration.py -q -p no:cacheprovider
& $py github_upload/check_setup.py --out "github_upload/outputs/team_render_$run"
```

预期16 passed；render保存setup_report.json与reacher_preview.png。先数值后渲染，后者失败不否认数值结果。若pytest临时目录权限出错，用自己有权限的`--basetemp`新目录，保留错误信息。

## 演示与看结果

```powershell
Invoke-Item github_upload/outputs/final_acceptance_20261118/demo_boundary_v2/replay.html
& $py github_upload/presentation_demo.py --scenario boundary --out "github_upload/outputs/team_demo_$run" --open
Invoke-Item FINAL_ACCEPTANCE.md
Invoke-Item SLIDES_CONTENT.md
Invoke-Item github_upload/outputs/final_acceptance_20261118/figures
```

四种单独模式及录屏脚本见DEMO_GUIDE.md。图表解释见FIGURE_GUIDE，口语稿见SPEAKER_NOTES，问答见QA_PREP。包中的原始CSV可核算成功计数；全量日志审计需要保留全证据的原项目。

## 常见错误

- `ModuleNotFoundError`：检查`$py`指向解压项目的.venv，不是仅激活了mp1或WindowsApps占位解释器。
- Torch/SB3冲突：使用包内CPU锁，执行pip check；不要复用未经核对的旧Torch2.7。
- `Output directory exists`：换全新时间戳；不要删除原结果来重跑。
- OpenGL/GLFW失败：先跑numeric-only；使用已经生成的GIF/静态图备份；不照搬Linux EGL设置。
- HTML没有关联应用：在浏览器中打开本地replay.html，或直接查看PNG；GIF不是MP4。
- 路径含空格：引号包住路径，使用PowerShell调用运算符`&`；保持包内相对目录结构。
- 接手包没有traces：这是有意精简，完整日志位置在本页开头；不删除其证据索引。

## 另一位组员必须亲自完成的检查（待完成）

- [ ] 记录姓名、日期、另一台电脑型号/系统/Python版本；明确是否真的是第二台电脑。
- [ ] 验证PACKAGE_MANIFEST的文件哈希，完成安装与pip check。
- [ ] 数值四模式结果吻合，保存新run_status、CSV、命令和失败日志。
- [ ] 渲染/回放可看清模式、时间、攻击窗、距离、报警与中止。
- [ ] 五张图、分母、截断说明和4条失败身份可以解释。
- [ ] 返回验证记录给小组，由小组确认；本轮未发送任何消息。
- [ ] 全组填写真实成员贡献、做一次12分钟计时彩排、核实Moodle提交要求。

当前状态：同一电脑上的本地打包解压烟雾检查即使通过，也**不算跨电脑复现**。第二成员/第二电脑暂无验证记录，不能预填通过。
