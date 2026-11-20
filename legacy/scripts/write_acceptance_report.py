import json
from pathlib import Path
import pandas as pd
from final_acceptance import ROOT,OUT

def table(f):
    return '| '+' | '.join(f.columns)+' |\n|'+'|'.join(['---']*len(f.columns))+'|\n'+'\n'.join('| '+' | '.join(str(v) for v in row)+' |' for row in f.itertuples(index=False,name=None))

def main():
    result=json.loads((OUT/'acceptance.json').read_text()); f=pd.read_csv(OUT/'four_failures.csv'); rates=pd.read_csv(OUT/'false_alarms.csv');w=pd.read_csv(OUT/'window_rates.csv');t=pd.read_csv(OUT/'verified_episodes.csv')
    historical=pd.read_csv(ROOT/'outputs/main_v1/episodes.csv');hc=historical[(historical.case=='clean')&historical.monitor_on]
    clean=rates[rates.variant=='original'];alarms=int(clean.alarms.sum());opportunities=int(clean.opportunities.sum());episodes=int(clean.episodes.sum());episodealarms=int(clean.episodes_with_alarm.sum())
    checks=[('短攻击计数','PASS','none 1080/1080; original 1076/1080; grace1 1080/1080','short_totals.csv'),
            ('4次中止身份及独立性','PASS','4条失败记录，4个不同(policy,seed)，不是4次独立训练策略证据','four_failures.csv'),
            ('持续攻击','PASS','原/改进各73/90中止；73对身份一致；无防御90/90成功','sustained_pairs.csv; cohorts.csv'),
            ('额外响应延迟','PASS','73对全部+1步，dt=.02s，即20ms','sustained_pairs.csv; acceptance.json'),
            ('报警分母','PASS WITH QUALIFICATION',f'新正常逐步{alarms}/{opportunities}={alarms/opportunities:.6%}；整回合{episodealarms}/{episodes}={episodealarms/episodes:.2%}；每条件窗口n=90','false_alarms.csv; window_rates.csv'),
            ('截断窗口','CORRECTED METADATA','短攻击报警观测窗全部完整：中止观测也完成检测。原方法3个攻击动作窗未完成，4个攻击动作+后10步距离窗不完整；持续两方法各73报警窗截断','paired_windows.csv; verified_episodes.csv'),
            ('中止轨迹','PASS','全部中止算任务失败；最终距离统计仅完整100步；另列中止数，完整轨迹均值仍有幸存者选择','verified_episodes.csv; presentation_cohorts.csv'),
            ('seed划分','PASS','开发18状态、测试90状态、探索校准300状态、验证/正式/已核对pilot状态集合互斥','acceptance.json; seed_inventory.json'),
            ('配对初始状态、噪声、攻击日程','PASS','逐步重算；相同(policy,seed)初始真值一致，噪声误差<1e-13m，delta逐步核对','acceptance.json; final_acceptance.py'),
            ('源码、模型、配置映射','PASS','两个运行目录的执行快照逐文件SHA256吻合；3个模型吻合；正式plan哈希吻合','acceptance.json; protected_before.json'),
            ('冻结顺序','SUPPORTED, NOT CERTIFIED','开发分数15/15，预声明平局选1；执行源码先写选择后测试。可变本地文件不能独立认证当时时序，不声称外部预注册','frozen_selection.json; executed source/exploration.py'),
            ('课程要求','FOUND','已读取上级目录正式要求：12分钟含demo+3分钟Q&A，8分rubric。Moodle日期/截止/报告格式待核实','DASE7508_Final_Project_Presentation_Instructions.txt'),
            ('跨电脑复现','PENDING','没有第二位组员/第二台电脑验证记录；本机多环境不算跨电脑复现','TEAM_HANDOFF.md'),
            ('视频与人工演练','PENDING','已生成MuJoCo四模式GIF/HTML注释回放；未生成桌面录屏MP4，未做五人计时彩排','DEMO_GUIDE.md')]
    report='''# Final acceptance / 最终验收

验收结论：**实验数字与关键语义通过；presentation内容草稿与本机回放可交付。人工验收事项未完成，不能称最终提交已获课程认可。**

本次未训练、未新增攻击、未搜索参数、未修改实验决策代码。只新增只读验收/作图脚本与独立展示入口。先读取项目报告及最新材料索引；项目和适用祖先未找到AGENTS.md。原目录包含Windows不可读pytest临时目录，已排除这些无关目录后查找材料；未删除它们。

验收主要数据：github_upload/outputs/exploratory_20261118_compatible/test，以及reproduction_20261118_compatible_main。全部数值从episodes.csv和完整traces.jsonl.gz重新计算，不以旧报告作依据。逐步共检查3780回合/369446行和4500回合/449882行。旧环境重复运行未合并为新增样本。

下列证据文件除另注明外均在github_upload/outputs/final_acceptance_20261118/。

'''+table(pd.DataFrame(checks,columns=['检查对象','状态','结果及限制','证据']))+'\n\n## 四条避免中止的记录\n\n'+table(f)+f'''

这四条是4个不同的配对初始状态；仍只有3个训练策略。每状态在12个短攻击条件重复评估，所以1080是90×12个条件试验，不是1080个独立初始状态。历史两个中止则是同一(policy3,802009)在bias与random_bias下重复，不能称两个独立状态。

正常新测试两方法均报警{alarms}次，分母是90×99={opportunities}个可检测观测（初始观测0不计报警机会），整回合有报警{episodealarms}/90。历史正常逐步{int(hc.alarm_count.sum())}/{int(hc.detection_steps.sum())}={hc.alarm_count.sum()/hc.detection_steps.sum():.6%}，整回合{int(hc.any_alarm.sum())}/90。禁止混用历史63/90与新测试54/90。

窗口分母按单一攻击条件的90个配对状态计算，正常窗口只复用同一条清洁轨迹。短攻击正常窗口报警13/90（start20）或17/90（start50/70）；攻击窗口至少一次报警76/90至90/90。首次报警延迟仅在窗口内曾报警者平均；无报警另列。短攻击的报警观测窗全部完整；中止观测已处理，只是没有再执行动作。持续攻击每种防御73个报警窗截断，不能把未观察后缀认作无报警。持续攻击虽100%至少一次观察报警，仍有17/90没有达到连续中止边界；报警和中止不是一个指标。

发现的展示/文档问题：旧图沿用初次旧Torch排错结果；旧complete_windows按完成动作数判断，却用于说明报警窗口完整性，混淆了中止观测和未执行动作；提纲正文11分20秒只留40秒换人。现从兼容运行重作五图，独立计算检测观测暴露、攻击动作距离窗和后续10步距离窗，正文11分钟另留1分钟。窗口元数据说明已纠正，主要成功数、报警率与响应差异不变；不需要重跑实验。

精确的4条新失败中，step39/89是攻击末步前后报警链已从前一噪声样本开始，step90是窗口结束后延伸；逐步日志证据保留。一步等待只是中止边界延后，不增强报警识别能力。避免中止不等于优于无防御。

来源与时序限制：执行源码快照和模型可验哈希一致性，但快照不是独立审计机构的时间戳；探索配置没有完整逐包运行版本表，其兼容环境来源由已有重跑命令/日志和包清单支持。不得把这些元数据说成外部认证。

课程要求原PDF位于项目外上级目录，已只读提取全文并存哈希于course_sources.json。不是根据文件名猜要求。要求明确允许live demo、recording或annotated trace；本次提供最后一种。提交日期、顺序和deadline仍按Moodle，由小组核实。本机回放不是跨电脑复现。
'''
    (ROOT.parent/'FINAL_ACCEPTANCE.md').write_text(report,encoding='utf-8')
    inventory=result['seed_sets'].copy()
    for label,run in [('main_calibration',ROOT/'outputs/reproduction_20261118_compatible_main'),('pilot_calibration',ROOT/'outputs/pilot_checked_20261022')]:
        cal=json.loads((run/'calibration.json').read_text());s={v for c in cal.values() for v in c['seeds']}
        assert not s&set(t.seed)
        inventory[label]=dict(count=len(s),minimum=min(s),maximum=max(s))
    (OUT/'seed_inventory.json').write_text(json.dumps(inventory,indent=2),encoding='utf-8')
    print('FINAL_ACCEPTANCE.md generated')

if __name__=='__main__':main()
