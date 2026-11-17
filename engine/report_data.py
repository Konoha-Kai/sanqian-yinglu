"""Turn measured evidence and optional reviewed notes into the browser's data."""

from exchange_verdict import verdict


def reviewed_action(note):
    return dict(note, grade='known', verdict=verdict(note.get('facts')))


def make_round(data, options, number, timers=()):
    folder = f'round-{number}'
    config = data['config']
    combat = data['combatAnalysis']
    names = options.get('players', {})
    players = [dict(name=names.get(side, f'{side} 方')) for side in 'AB']
    notes = options.get('actions', [])
    actions = [reviewed_action(note) for note in notes]
    for timer in timers:
        if timer['slot'] == '奥义' or timer['kind'] == 'timer_reacquired':
            continue
        if overlaps(timer, actions):
            continue
        label = {'opening': '开局已有冷却', 'timer_restart': '倒计时上跳',
                 'timer_start': '读到倒计时'}[timer['kind']]
        actions.append(dict(
            time=timer['time'], side=timer['side'], slot=timer['slot'], grade='timer',
            title=label, origin='HUD 数字，待核', verdict=verdict(supports_timer=True),
            result=f'表盘读到 {timer["value"]}。重新释放、强化刷新或读取缺口需要分别复核。'))

    measured = {event['eventId']: event for event in combat['actions']}
    for observed in combat['actions']:
        if overlaps(observed, actions):
            continue
        detail = '同期有对手掉血线索。' if observed['outgoingIds'] or observed['closeOrderIds'] else '没有匹配到明确的对手掉血线索。'
        actions.append(dict(
            time=observed['time'], side=observed['side'], slot=observed['slot'], grade='color',
            title=observed['kind'], origin='HUD 颜色，待核', verdict=verdict(),
            evidencePath=f"{folder}/{observed['evidencePath']}",
            result=detail + '对照回放判断释放及效果。'))

    events = []
    for action in notes:
        events.append(dict(
            time=action['time'], window=f"{action['time']:.1f} 秒", title=action['title'],
            summary=action['result'], effect=action['result'], hud=action['origin'],
            library=' → '.join(action.get('phases', []))))
    for drop in combat['damage']:
        related = [measured[key] for key in drop['candidateIds'] + drop['closeOrderIds']]
        slots = '、'.join(dict.fromkeys(e['slot'] for e in related))
        events.append(dict(
            time=drop['time'], window=f"{drop['time']:.1f} 秒", title=f"{drop['side']} 方出现掉血",
            summary=f"可见血条填充减少约 {drop['drop'] * 100:.1f} 个百分点。",
            effect=f'附近的资源线索包括{slots}，伤害来源待核。' if slots else '伤害来源待核，可回看普攻和延迟技能。',
            hud='血条颜色观察', evidencePath=f"{folder}/{drop['evidencePath']}"))
    if not events:
        events = [dict(time=a['time'], window=f"{a['time']:.1f} 秒", title=f"{a['side']} · {a['slot']}",
                       summary=a['title'], effect=a['result'], hud=a['origin'],
                       evidencePath=a.get('evidencePath')) for a in actions]

    trees = options.get('trees')
    if trees is None:
        trees = [observation_tree(drop, measured) for drop in combat['damage']]
    return dict(
        label=options.get('label', f'第 {number} 回合'),
        match=f'{players[0]["name"]} vs {players[1]["name"]}',
        sources=players, resultsPath=f'{folder}/results.json',
        events=sorted(events, key=lambda event: event['time']), trees=trees,
        tracks=dict(
            start=config['start'], end=config['end'], times=data['times'], hp=data['hp'],
            slots=config['dials'], damage=combat['damage'],
            actions=sorted(actions, key=lambda action: action['time']),
            states=[segment for segment in data['segments']
                    if segment['state'] in ('暗底黄色点缀', '灰暗')]))


def overlaps(item, actions):
    return any(action['side'] == item['side'] and action['slot'] == item['slot']
               and action['time'] - .55 <= item['time'] <= action.get('end', action['time']) + .55
               for action in actions if action['grade'] != 'color')


def observation_tree(drop, measured):
    ids = drop['candidateIds'] + drop['closeOrderIds']
    previous = [measured[key] for key in ids if measured[key]['time'] <= drop['time']]
    path = [dict(side=entry['side'], time=entry['time'], label='图标线索',
                 title=f'{entry["slot"]} · {entry["kind"]}',
                 text='这一项与掉血的时间相近。是否释放、是否造成这次伤害需回看。')
            for entry in sorted(previous, key=lambda entry: entry['time'])]
    time = drop['time']
    path.append(dict(side=drop['side'], time=time, label='血条观察', title='可见血条下降',
                     text=f"约减少 {drop['drop'] * 100:.1f} 个血条填充百分点。"))
    return dict(time=time, short=f"{drop['side']} 方掉血", context='检查掉血前的动作',
                path=path, outcome=dict(label='当前证据', title='伤害来源待核',
                text='确认命中、控制或打断后，才补充实战走法和可选分支。'))
