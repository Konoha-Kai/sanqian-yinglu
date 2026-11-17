"""Colour-only offline onset candidates, refined to source decode frames."""
from pathlib import Path
import cv2
import numpy as np

RULES={'chain_gap_seconds':1.5,'reset_quiet_seconds':1.2,'resource_lookback_seconds':1.0,
       'minimum_sustained_span':.35,'minimum_total_drop':.025,'step_confirm_frames':3,
       'note':'阈值是可调筛选规则，不是游戏机制帧数。多个掉血段可属于同一受控过程；持续伤害也可能没有控制。'}

def locate_step(times,values,coarse,bar_width):
 """Find earliest persistent one-pixel loss, confirmed by a larger later loss."""
 lo=np.searchsorted(times,coarse-.45);hi=np.searchsorted(times,coarse+.8)
 if hi-lo<8:return None
 baseline=float(np.median(values[lo:min(lo+8,hi)]));pixel=1/bar_width
 for i in range(lo+1,hi-5):
  loss=baseline-values[i]
  if loss<pixel*.9:continue
  if values[i-1]<=baseline-pixel*.9:continue
  if np.sum(values[i:i+4]<=baseline-pixel*.9)<3:continue
  future=values[i:min(hi,i+15)]
  if baseline-float(np.median(future[-4:]))<max(.012,pixel*1.8):continue
  # Do not accept a transient colour loss that immediately recovers.
  if np.median(values[i+3:i+7])>baseline-pixel*.9:continue
  return dict(index=int(i),baseline=baseline,firstValue=float(values[i]),lastUnchangedIndex=int(i-1))
 return None

def group_chains(damages,substitutions):
 chains=[]
 for e in sorted(damages,key=lambda e:e['start']):
  previous=chains[-1] if chains else None
  separated=previous is None or previous['victim']!=e['side'] or e['start']-previous['end']>RULES['chain_gap_seconds']
  if previous and any(previous['start']<s['start']<=e['start'] and s['side']==e['side'] for s in substitutions):separated=True
  if separated:chains.append({'victim':e['side'],'attackerCandidate':'B' if e['side']=='A' else 'A','start':e['start'],'end':e['end'],'damageEvents':[e]})
  else:previous['damageEvents'].append(e);previous['end']=max(previous['end'],e['end'])
 return chains

def refine(payload,root):
 from analyse_color import hud_height,measure
 cfg=payload['config'];cap=cv2.VideoCapture(cfg['source']);rows=[];frame_index=-1
 hud_bottom=hud_height(cfg)
 while True:
  ok,frame=cap.read()
  if not ok:break
  frame_index+=1;t=cap.get(cv2.CAP_PROP_POS_MSEC)/1000
  if t>cfg['end']+.5:break
  if t<max(0,cfg['start']-.7):continue
  hsv=cv2.cvtColor(frame[:hud_bottom],cv2.COLOR_BGR2HSV);m=measure(hsv,cfg)
  rows.append({'time':t,'sourceFrame':frame_index+1,'A':m['A_hp'],'B':m['B_hp']})
 cap.release();times=np.array([r['time'] for r in rows]);hp={s:np.array([r[s] for r in rows]) for s in ['A','B']}
 subs=[e for e in payload['events'] if e['type']=='表盘变化' and e.get('slot')=='替身' and e.get('after')=='暗底黄色点缀' and e.get('before') in ['基准色','彩色']]
 damage=[e for e in payload['events'] if e['type']=='血条下降']
 chains=group_chains(damage,subs);out=[];wanted={}
 for chain in chains:
  victim=chain['victim'];parts=chain.pop('damageEvents');total=sum(e['drop'] for e in parts)
  continuous=len(parts)>=2 or (chain['end']-chain['start']>=RULES['minimum_sustained_span'] and total>=RULES['minimum_total_drop'])
  prior=[e['end'] for e in damage if e['end']<chain['start']]
  quiet=chain['start']-max(prior,default=cfg['start'])
  width=cfg['hp'][victim][2]-cfg['hp'][victim][0];point=locate_step(times,hp[victim],chain['start'],width)
  chain.update(id=f'O{len(out)+1:02d}',damageEventIds=[e['id'] for e in parts],drop=round(total,4),damageSegments=len(parts),quietSeconds=round(quiet,3),sustained=continuous,
    classification='连续掉血支持的起手候选' if continuous else '单次掉血，控制证据不足',controlConfirmed=False,
    reviewStatus='待确认受控；颜色不能证明无法自行移动',source='仅 HUD 颜色',frame=None)
  nearby_sub=[s for s in subs if s['side']==victim and chain['start']<=s['start']<=chain['end']+.8]
  chain['substitutionEvidence']=[{'time':s['start'],'eventId':s['id'],'meaning':'受击侧替身表盘进入暗色样式；支持资源使用候选，不证明脱身成功'} for s in nearby_sub]
  chain['opponentResources']=[{'time':e['start'],'slot':e['slot'],'eventId':e['id']} for e in payload['events'] if e['type']=='表盘变化' and e['side']==chain['attackerCandidate'] and e.get('after') in ['灰暗','暗底黄色点缀'] and e.get('before') in ['基准色','彩色'] and chain['start']-RULES['resource_lookback_seconds']<=e['start']<=chain['start']+.2]
  chain['priority']='优先复核' if continuous and (quiet>=RULES['reset_quiet_seconds'] or nearby_sub) else '普通复核'
  if point:
   i=point['index'];previous=rows[i-1];r=rows[i]
   chain['frame']={'number':r['sourceFrame'],'time':round(r['time'],6),'interval':[round(previous['time'],6),round(r['time'],6)],'previousNumber':previous['sourceFrame'],
     'meaning':'本段首次可检测且后续持续的血条颜色下降帧；不是已确认的技能碰撞帧或受控起始帧。','indexConvention':'源视频顺序解码帧号，从 1 开始；时间取源视频解码时间戳。'}
   indices=[max(0,i-1),i,min(len(rows)-1,i+1),min(len(rows)-1,i+6)]
   chain['evidence']=[{'number':rows[j]['sourceFrame'],'time':round(rows[j]['time'],6),'path':f'onset-evidence/frame-{rows[j]["sourceFrame"]:06d}.jpg'} for j in indices]
   for j in indices:wanted[rows[j]['sourceFrame']]=None
   low=max(0,i-35);high=min(len(rows),i+65)
   chain['detailTrace']=[{'time':round(rows[j]['time'],6),'number':rows[j]['sourceFrame'],'A':rows[j]['A'],'B':rows[j]['B']} for j in range(low,high)]
  else:chain['frameNote']='未通过逐帧持续下降检查，不输出精确起始帧。'
  out.append(chain)
 # Second pass writes only requested evidence frames; memory remains bounded.
 folder=Path(root)/'onset-evidence';folder.mkdir(exist_ok=True);cap=cv2.VideoCapture(cfg['source']);n=0
 while wanted:
  ok,frame=cap.read();n+=1
  if not ok:break
  if n in wanted:
   ok,encoded=cv2.imencode('.jpg',frame[:hud_bottom]);assert ok
   encoded.tofile(str(folder/f'frame-{n:06d}.jpg'));wanted.pop(n)
 cap.release()
 if wanted:raise RuntimeError('Missing requested source frames')
 return {'rules':RULES,'sourceFramesMeasured':len(rows),'candidates':out,'frameMeaning':'定位 HUD 伤害显示起点，不能从颜色证明控制成立或精确碰撞时刻。'}
