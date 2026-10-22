"""Training-return curves and separate clean-validation distances."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('directories',nargs='+',type=Path)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    fig,axes=plt.subplots(1,2,figsize=(12,4),constrained_layout=True)
    for index,directory in enumerate(args.directories):
        with (directory/'train.monitor.csv').open() as file:
            next(file)  # SB3's metadata comment.
            rows=list(csv.DictReader(file))
        steps=np.cumsum([int(r['l']) for r in rows])
        returns=pd.Series([float(r['r']) for r in rows]).rolling(100,min_periods=10).mean()
        axes[0].plot(steps,returns,label=directory.name,color=f'C{index}')
        validation=directory/'validation.json'
        if validation.exists():
            data=json.loads(validation.read_text())
            errors=[t['final_10_mean_distance']*100 for t in data['trials']]
            axes[1].scatter(index+np.linspace(-.12,.12,len(errors)),errors,color=f'C{index}',s=20)
            axes[1].text(index,max(errors)+.12,f'{data["validation_successes"]}/{data["validation_episodes"]}',ha='center')
    axes[0].set_xlabel('Environment steps'); axes[0].set_ylabel('100-episode rolling training return')
    axes[0].set_title('Exploratory training policy; higher is better'); axes[0].legend(fontsize=7)
    axes[1].axhline(3,color='black',ls='--',label='3 cm success threshold')
    axes[1].set_xticks(range(len(args.directories)),[p.name for p in args.directories],rotation=15,fontsize=8)
    axes[1].set_ylabel('Final-ten-step mean true distance (cm)')
    axes[1].set_title('30 independent clean validation episodes per policy'); axes[1].legend(fontsize=7)
    for ax in axes: ax.grid(alpha=.2)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(args.out,dpi=170); plt.close(fig)
    print(args.out)


if __name__=='__main__':
    main()
