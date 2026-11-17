"""Keep release, contact and effects independent when combining replay evidence."""


def verdict(facts=None, *, supports_timer=False):
    facts = facts or {}
    contact = facts.get('contact', '待核')
    control = facts.get('control', '待核')
    duration = facts.get('selfEscape', '待核')
    if contact == '未命中' or control == '未造成控制':
        opening = '未形成起手'
    elif contact == '命中' and control == '受控' and duration == '无法自行脱身':
        opening = '起手成立'
    else:
        opening = '起手待核'

    return {
        'release': facts.get('release', '有倒计时线索' if supports_timer else '仅图标线索'),
        'contact': contact,
        'movement': facts.get('movement', '待核'),
        'control': control,
        'interruption': facts.get('interruption', '待核'),
        'damage': facts.get('damage', '归属待核'),
        'opening': opening,
    }
