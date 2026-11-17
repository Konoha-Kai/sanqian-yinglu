"""Associate colour-only resource events with subsequent damage-chain entries."""
OFFENSIVE={'一技能','二技能','三技能','秘卷','通灵','奥义'}
LOOKBACK=1.5

def resource_changes(payload):
 out=[]
 for e in payload['events']:
  if e['type']!='表盘变化' or e.get('slot') not in OFFENSIVE:continue
  before,after=e.get('before'),e.get('after');kind=None
  if before in ['基准色','彩色'] and after in ['灰暗','暗底黄色点缀']:
   kind='使用样式变化'
  elif before=='基准色' and after=='彩色':
   # A skill can change to another action stage without a grey cooldown icon.
   base=payload['baselines'][e['side']+'_'+e['slot']];m=e.get('features',{})
   delta=max(abs(m.get(k,base[k])-base[k]) for k in ['dark','chroma','white'])
   if delta>=.18:kind='图标形态变化 / 子阶段候选'
  if not kind:continue
  # Ultimate overlay colours often change with energy; they alone do not show casting.
  if e['slot']=='奥义':kind='奥义表盘变化，可能是能量 / 禁用变化'
  out.append({'eventId':e['id'],'side':e['side'],'slot':e['slot'],'time':e['start'],'kind':kind,
              'before':before,'after':after,'evidencePath':'evidence/'+e['id']+'.jpg'})
 return out

def attribute(payload):
 actions=resource_changes(payload)
 for chain in payload['onsetAnalysis']['candidates']:
  damage_time=chain['frame']['time'] if chain.get('frame') else chain['start']
  candidates=[];later=[];prior_chain=[]
  for action in actions:
   if action['side']!=chain['attackerCandidate']:continue
   delay=damage_time-action['time']
   if 0<=delay<=LOOKBACK:
    previous=[e for e in payload['events'] if e['type']=='血条下降' and e['side']==chain['victim'] and e['id'] not in chain['damageEventIds'] and e['start']<chain['start'] and e['start']<=action['time']<=e['end']]
    if previous:
     prior_chain.append(dict(action,reason='发生在更早伤害段内部，可能为连招 / 进入冷却，不重复作为新起手证据'))
     continue
    candidates.append(dict(action,delay=round(delay,3),caution='只有时序与颜色支持，未独立证明命中'))
   elif -.25<=delay<0:later.append(dict(action,delay=round(delay,3)))
  candidates.sort(key=lambda a:a['time'])
  plausible=[a for a in candidates if a['slot']!='奥义']
  slots=list(dict.fromkeys(a['slot'] for a in plausible))
  if len(slots)==1:
   label=slots[0]+'起手候选' if chain['sustained'] else slots[0]+'命中候选'
   status='单一资源关联';primary=slots[0]
  elif slots:
   label=' / '.join(slots)+'：起手来源待区分' if chain['sustained'] else ' / '.join(slots)+'：伤害来源待区分'
   status='多个资源，暂不唯一归因';primary=None
  else:label='未匹配到起手资源';status='可能是普攻、延迟伤害或图标变化漏检';primary=None
  chain['resourceAttribution']={'damageTime':round(damage_time,3),'lookbackSeconds':LOOKBACK,'label':label,'status':status,
    'primaryResourceCandidate':primary,'candidates':candidates,'afterDamageHints':later,'priorChainHints':prior_chain,'causalityConfirmed':False,
    'sequence':[{'time':a['time'],'side':a['side'],'kind':a['kind'],'label':a['slot']} for a in candidates]+
      [{'time':round(damage_time,3),'side':chain['victim'],'kind':'血条下降','label':'首次可见掉血'},
       {'time':chain['end'],'side':chain['victim'],'kind':'后续结果','label':'继续掉血' if chain['sustained'] else '单段掉血'}]+
      [{'time':s['time'],'side':chain['victim'],'kind':'脱身线索','label':'替身表盘变化'} for s in chain['substitutionEvidence']]}
 payload['onsetAnalysis']['resourceMethod']='攻击侧进攻资源颜色变化 → 对侧掉血 → 后续持续下降 / 替身线索。恢复颜色不计为释放；多个资源不强行唯一归因；命中后变化单列。'
 return payload
