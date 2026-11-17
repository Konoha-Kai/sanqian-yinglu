"""Link observed HUD events in both directions without inferring contact or control."""

from attribute_resources import LOOKBACK, resource_changes

# The sampled and smoothed HUD can shift the order of nearby observations.
ORDER_TOLERANCE = .25
SWAP_WINDOW = .6
SIDES = {'A': 'B', 'B': 'A'}


def judge_combat(payload):
    events = payload['events']
    onset_chains = payload['onsetAnalysis']['candidates']
    substitutions = [event for event in events if event['type'] == '表盘变化'
                     and event.get('slot') == '替身'
                     and event.get('before') in ('基准色', '彩色')
                     and event.get('after') == '暗底黄色点缀']
    actions = [dict(action, kindCode='ultimate_hint' if action['slot'] == '奥义' else 'resource')
               for action in resource_changes(payload)]
    actions.extend(dict(eventId=event['id'], side=event['side'], slot='替身',
                        time=event['start'], kind='替身资源线索', kindCode='substitution',
                        evidencePath=f"evidence/{event['id']}.jpg") for event in substitutions)
    actions.sort(key=lambda action: action['time'])

    chain_starts = {chain['damageEventIds'][0]: chain for chain in onset_chains}
    damage = []
    for event in events:
        if event['type'] != '血条下降':
            continue
        chain = chain_starts.get(event['id'])
        onset = chain.get('frame') if chain else None
        damage.append(dict(eventId=event['id'], side=event['side'], drop=event['drop'],
                           time=round(onset['time'], 3) if onset else event['start'],
                           end=event['end'], candidateIds=[], closeOrderIds=[], continuationIds=[],
                           evidencePath=(chain['evidence'][1]['path'] if onset else
                                         f"evidence/{event['id']}.jpg")))

    end = payload['config']['end']
    for action in actions:
        time = action['time']
        target = SIDES[action['side']]
        action['outgoingIds'] = []
        action['incomingIds'] = []
        action['closeOrderIds'] = []
        action['activeDamageIds'] = []
        action['continuationDamageIds'] = []
        action['truncated'] = time + LOOKBACK > end
        for drop in damage:
            delay = drop['time'] - time
            if -ORDER_TOLERANCE <= delay <= LOOKBACK and drop['side'] == action['side']:
                action['incomingIds'].append(drop['eventId'])
            if drop['side'] != target:
                continue
            if drop['time'] < time <= drop['end']:
                action['activeDamageIds'].append(drop['eventId'])

    for action in actions:
        if action['kindCode'] != 'resource':
            continue
        target = SIDES[action['side']]
        time = action['time']
        for drop in damage:
            if drop['side'] != target:
                continue
            delay = drop['time'] - time
            if ORDER_TOLERANCE < delay <= LOOKBACK:
                if action['activeDamageIds']:
                    action['continuationDamageIds'].append(drop['eventId'])
                    drop['continuationIds'].append(action['eventId'])
                else:
                    action['outgoingIds'].append(drop['eventId'])
                    drop['candidateIds'].append(action['eventId'])
            elif abs(delay) <= ORDER_TOLERANCE:
                action['closeOrderIds'].append(drop['eventId'])
                drop['closeOrderIds'].append(action['eventId'])

    for action in actions:
        time = action['time']
        target = SIDES[action['side']]
        action['contextIds'] = [other['eventId'] for other in actions
                                if other['side'] == target
                                and -LOOKBACK <= other['time'] - time <= LOOKBACK]
        action['recentIncomingIds'] = [drop['eventId'] for drop in damage
                                       if drop['side'] == action['side']
                                       and drop['time'] <= time <= drop['end'] + LOOKBACK]
        action['targetQualityIds'] = [event['id'] for event in events
                                      if event['type'] == '质量提示' and event['side'] == target
                                      and event['start'] <= time + LOOKBACK and event['end'] >= time]

    for drop in damage:
        drop['oppositeDamageIds'] = [other['eventId'] for other in damage
                                     if other['side'] != drop['side']
                                     and abs(other['time'] - drop['time']) <= SWAP_WINDOW]

    return {'lookbackSeconds': LOOKBACK, 'orderToleranceSeconds': ORDER_TOLERANCE,
            'analysisEnd': end, 'actions': actions, 'damage': damage}
