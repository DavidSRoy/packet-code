"""Plot paired simulation metrics; no real-flight improvement is implied."""
import json,sys
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
H=Path(__file__).resolve().parent
rows=json.loads((H/'results.json').read_text())
fig,axs=plt.subplots(1,3,figsize=(11,3.8),layout='constrained')
for ax,(key,title,unit) in zip(axs,[('tilt_1_3_rms_deg','Visible rocking, 1–3 Hz','combined roll/pitch RMS (degrees)'),('xy_rms_mm','Position hold','true horizontal error RMS (mm)'),('z_rms_mm','Height hold','true vertical error RMS (mm)')]):
 for i,(label,group,color) in enumerate([('v6','v6','#6f7e89'),('v7 candidate','v7','#0695b5')]):
  vals=[r['score'][key] for r in rows if (r['name'].startswith('v7val_nom') or r['name'].startswith('v7final_nom')) and r['name'].endswith('_'+group) and 'score' in r]
  ax.bar(i,np.mean(vals),color=color,width=.55)
  ax.scatter(np.full(len(vals),i),vals,color='black',s=17,zorder=3)
  ax.text(i,max(vals)*1.06,f'{np.mean(vals):.3f}' if 'deg' in key else f'{np.mean(vals):.2f}',ha='center')
 ax.set_xticks([0,1],['v6','v7 candidate']);ax.set_title(title);ax.set_ylabel(unit);ax.set_ylim(bottom=0,top=ax.get_ylim()[1]*1.15);ax.spines[['top','right']].set_visible(False)
fig.suptitle('Paired SITL comparison on the updated model · 3 seeds · 10 cm hover\nSimulation results only; v7 has not flown',fontsize=12)
fig.savefig(sys.argv[1],dpi=180)
