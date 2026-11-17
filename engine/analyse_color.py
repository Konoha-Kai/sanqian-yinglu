"""Read colour changes in the health bars and resource icons."""
from pathlib import Path
import json, csv
import cv2
import numpy as np

DEFAULT={
 'start':3.0,'end':44.5,'sample_hz':15,'reference_size':[1280,568],
 'hp':{'A':[149,35,321,42],'B':[925,35,1102,42]},
 'dials':{'A':{'通灵':[187,125],'替身':[255,125],'秘卷':[319,125],'一技能':[383,125],'二技能':[447,125],'奥义':[509,125]},
          'B':{'通灵':[1090,125],'替身':[1026,125],'秘卷':[962,125],'一技能':[898,125],'二技能':[834,125],'奥义':[770,125]}},
 'radius':18,'hp_hue_max':16,'hp_saturation_min':140,'hp_value_min':130,
 'dark_value_max':85,'chromatic_saturation_min':100,'chromatic_value_min':100,
 'cool_dark_min':.27,'cool_chroma_max':.38,'cool_yellow_min':.008,
 'hold_samples':3,'median_samples':5,'hp_drop_min':.012,'damage_merge_gap':.4,'quiet_seconds':1.2,
 'scope_note':'按回合分析；新布局请重新定位并校准颜色阈值。'}

def median(a,k):
 return np.array([np.median(a[max(0,i-k//2):min(len(a),i+k//2+1)],axis=0) for i in range(len(a))])

def hud_height(cfg):
 dials_bottom=max(y+cfg['radius']+2 for slots in cfg['dials'].values() for x,y in slots.values())
 return max(160,dials_bottom,max(box[3] for box in cfg['hp'].values()))

def measure(hsv,cfg):
 out={}
 for side,box in cfg['hp'].items():
  x1,y1,x2,y2=box;h,s,v=cv2.split(hsv[y1:y2,x1:x2]);red=((h<=cfg['hp_hue_max'])|(h>=174))&(s>=cfg['hp_saturation_min'])&(v>=cfg['hp_value_min'])
  out[side+'_hp']=float(np.mean(np.mean(red,axis=0)>=.5))
 for side,slots in cfg['dials'].items():
  for slot,(x,y) in slots.items():
   r=cfg['radius'];patch=hsv[y-r:y+r+1,x-r:x+r+1];yy,xx=np.ogrid[-r:r+1,-r:r+1];mask=xx*xx+yy*yy<r*r
   h,s,v=patch[mask].T
   out[side+'_'+slot]=dict(dark=float(np.mean(v<cfg['dark_value_max'])),chroma=float(np.mean((s>cfg['chromatic_saturation_min'])&(v>cfg['chromatic_value_min']))),yellow=float(np.mean((h>=18)&(h<=38)&(s>110)&(v>130))),white=float(np.mean((s<65)&(v>220))),value=float(np.median(v)))
 return out

def state(m,c,base):
 if m['white']>.48:return '过亮'
 if abs(m['dark']-base['dark'])<.10 and abs(m['chroma']-base['chroma'])<.12 and abs(m['white']-base['white'])<.15:return '基准色'
 if m['dark']>max(c['cool_dark_min'],base['dark']+.10) and m['chroma']<c['cool_chroma_max'] and m['yellow']>c['cool_yellow_min']:return '暗底黄色点缀'
 if m['chroma']<.20:return '灰暗'
 return '彩色'

def analyze(c, output, *, auto_hud=True):
 output=Path(output);output.mkdir(parents=True,exist_ok=True)
 if auto_hud:
  from locate_hud import locate
  c,_=locate(c)
 (output/'config.json').write_text(json.dumps(c,ensure_ascii=False,indent=2),encoding='utf-8')
 cap=cv2.VideoCapture(c['source'])
 if not cap.isOpened():raise ValueError('无法打开录像')
 rows=[];next_t=c['start'];frames={};hud_bottom=hud_height(c)
 while True:
  ok,im=cap.read()
  if not ok:break
  t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
  if t>c['end']:break
  if t+1e-6<next_t:continue
  next_t=t+1/c['sample_hz']-.008
  if [im.shape[1],im.shape[0]]!=c['reference_size']:raise ValueError('Resolution mismatch: recalibrate config; no silent coordinate scaling')
  hud=im[:hud_bottom];m=measure(cv2.cvtColor(hud,cv2.COLOR_BGR2HSV),c);m['time']=round(t,4);rows.append(m)
  frames[len(rows)-1]=hud.copy()
 cap.release()
 if not rows:raise ValueError('指定的时间范围内没有可分析的视频帧')
 times=np.array([r['time'] for r in rows]);events=[];traces={};segments=[];baselines={}
 for side in ['A','B']:
  raw=np.array([r[side+'_hp'] for r in rows]);hp=median(raw,c['median_samples']);traces[side]=np.round(hp,4).tolist()
  # Persistent step decreases; no cumulative-min trick that would hide colour recovery errors.
  changes=[]
  for i in range(5,len(hp)-4):
   before=float(np.median(hp[i-5:i]));after=float(np.median(hp[i:i+4]));drop=before-after
   if drop>=c['hp_drop_min']:
    if not changes or times[i]-changes[-1][-1]>c['damage_merge_gap']:changes.append([i,times[i]])
    else: changes[-1].extend([i,times[i]])
  prev_end=c['start']
  for group in changes:
   start_i=group[0];end_i=group[-2];before=float(np.median(hp[max(0,start_i-5):start_i]));after=float(np.median(hp[end_i:min(len(hp),end_i+4)]))
   quiet=times[start_i]-prev_end;prev_end=times[end_i]
   drop=max(0,before-after)
   future=hp[end_i:min(len(hp),end_i+int(c['sample_hz']*1.2))]
   recovered=len(future)>0 and np.max(future)-after>max(c['hp_drop_min'],drop*.6)
   events.append(dict(type='质量提示' if recovered else '血条下降',side=side,start=round(float(times[start_i]),3),end=round(float(times[end_i]),3),drop=round(drop,4),quiet=round(quiet,2),label='下降后快速恢复：遮挡 / 变色 / 回血待核' if recovered else '血条填充减少',level='待核' if recovered else '颜色观察',frameIndex=start_i))
  rises=np.where(np.diff(hp)>=c['hp_drop_min'])[0]
  for i in rises:
   events.append(dict(type='质量提示',side=side,start=round(float(times[i+1]),3),end=round(float(times[i+1]),3),label='血条红色占比回升：回血 / 遮挡 / 阈值误差待核',level='待核',frameIndex=int(i+1)))
  for slot in c['dials'][side]:
   key=side+'_'+slot;features=[r[key] for r in rows]
   initial=[m for t,m in zip(times,features) if c['start']+.2<=t<=c['start']+.6] or features[:5]
   base={k:float(np.median([m[k] for m in initial])) for k in features[0]};baselines[key]=base
   seq=[state(m,c,base) for m in features];current=seq[0];run_start=0;i=1
   while i<len(seq):
    if seq[i]!=current and len(seq[i:i+c['hold_samples']])==c['hold_samples'] and all(v==seq[i] for v in seq[i:i+c['hold_samples']]):
     new=seq[i];segments.append(dict(side=side,slot=slot,start=float(times[run_start]),end=float(times[i]),state=current))
     label='表盘颜色变化';level='颜色观察'
     if new=='暗底黄色点缀' and current in ['基准色','彩色','灰暗']:
      label='进入疑似倒计时样式：资源使用候选';level='候选，非确认释放'
     elif current=='暗底黄色点缀' and new in ['基准色','彩色']:label='离开暗底黄色点缀：恢复 / 形态切换候选'
     elif new=='灰暗' and current=='暗底黄色点缀':label='暗色样式内部变化：不重复计为释放'
     elif new=='灰暗':label='变灰：使用 / 禁用 / 子阶段候选';level='候选，非确认释放'
     elif new=='过亮' or current=='过亮':label='强光干扰：暂停解释';level='质量提示'
     events.append(dict(type='表盘变化',side=side,slot=slot,start=round(float(times[i]),3),end=round(float(times[min(i+c['hold_samples']-1,len(times)-1)]),3),before=current,after=new,label=label,level=level,frameIndex=i,features={k:round(v,3) for k,v in features[i].items()}))
     current=new;run_start=i;i+=c['hold_samples']
    else:i+=1
   segments.append(dict(side=side,slot=slot,start=float(times[run_start]),end=float(times[-1]),state=current))
 damage_events=sorted([e for e in events if e['type']=='血条下降'],key=lambda e:e['start'])
 last_damage_end=c['start']
 for e in damage_events:
  e['quiet']=round(max(0,e['start']-last_damage_end),3)
  last_damage_end=max(last_damage_end,e['end'])
  e['label']='双方血条稳定后下降：起手候选' if e['quiet']>=c['quiet_seconds'] else '持续 / 邻近伤害段'
 for e in events:
  if e['type']!='血条下降':continue
  nearby=[q for q in events if q['type']=='表盘变化' and abs(q['start']-e['start'])<.65 and q.get('after') in ['暗底黄色点缀','灰暗']]
  e['nearby']=[dict(side=q['side'],slot=q['slot'],time=q['start'],label=q['label']) for q in nearby]
  e['exchange']=any(q['type']=='血条下降' and q['side']!=e['side'] and abs(q['start']-e['start'])<.6 for q in events)
  e['interpretation']='邻近时刻双方掉血，只能判为伤害互换候选，不能据此确认顶技。' if e['exchange'] else '只确认该侧血条颜色占比下降；是否被控、谁的哪一招造成伤害，颜色不足以确定。'
 events.sort(key=lambda e:e['start']);evidence=output/'evidence';evidence.mkdir(exist_ok=True)
 for n,e in enumerate(events):
  e['id']=f'C{n+1:03d}';i=e.pop('frameIndex');ids=[max(0,i-4),i,min(len(rows)-1,i+4)]
  strip=np.vstack([frames[j] for j in ids]);encoded_ok,encoded=cv2.imencode('.jpg',strip)
  if not encoded_ok:raise RuntimeError('Evidence encoding failed')
  encoded.tofile(str(evidence/(e['id']+'.jpg')))
  e['evidenceTimes']=[rows[j]['time'] for j in ids]
 payload=dict(method='Fixed ROI + HSV pixel ratios + temporal median + persistent state transitions. No OCR, digit templates, neural models, action recognition or previous annotations as input.',config=c,baselines=baselines,times=times.round(3).tolist(),hp=traces,segments=segments,events=events,sampleCount=len(rows))
 from refine_onsets import refine
 payload['onsetAnalysis']=refine(payload,output)
 from attribute_resources import attribute
 attribute(payload)
 from judge_combat import judge_combat
 payload['combatAnalysis']=judge_combat(payload)
 (output/'results.json').write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding='utf-8')
 with (output/'measurements.csv').open('w',newline='',encoding='utf-8-sig') as f:
  flat=[]
  for row in rows:
   r={}
   for k,v in row.items():
    if isinstance(v,dict):r.update({k+'_'+j:z for j,z in v.items()})
    else:r[k]=v
   flat.append(r)
  writer=csv.DictWriter(f,fieldnames=list(flat[0]));writer.writeheader();writer.writerows(flat)
 return payload
