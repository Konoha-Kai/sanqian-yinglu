"""Read yellow HUD timer glyphs locally and track persistent changes."""

from collections import Counter
from pathlib import Path
import argparse
import json

import cv2
import numpy as np


def glyphs(frame, x, y, scale):
    rx, ry = round(18 * scale), round(20 * scale)
    patch = frame[y - ry:y + ry, x - rx:x + rx + 1]
    hsv = cv2.cvtColor(patch, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (16, 130, 140), (44, 255, 255))
    _, labels, stats, _ = cv2.connectedComponentsWithStats(mask)
    components = []
    for i, (left, top, width, height, area) in enumerate(stats[1:], 1):
        center_x = left + width / 2
        center_y = top + height / 2
        if not 11 * scale <= height <= 22 * scale or not 3 * scale <= width <= 15 * scale:
            continue
        if area < 21 * scale ** 2 or abs(center_x - rx) > 13 * scale or abs(center_y - ry) > 9 * scale:
            continue
        glyph = labels[top:top + height, left:left + width] == i
        norm = cv2.resize(glyph.astype('uint8'), (16, 24), interpolation=cv2.INTER_NEAREST)
        components.append((center_x, center_y, width / height, norm.astype(bool)))
    return sorted(components, key=lambda item: item[0])


def read_digit(glyph, templates):
    _, _, ratio, image = glyph
    scores = {}
    for digit, examples in templates.items():
        scores[digit] = max(
            (np.count_nonzero(image & template) / np.count_nonzero(image | template))
            - .37 * abs(ratio - reference_ratio)
            for reference_ratio, template in examples
        )
    best, runner = sorted(scores, key=scores.get, reverse=True)[:2]
    if scores[best] < .58 or scores[best] - scores[runner] < .055:
        return None
    return best


def timer(frame, x, y, scale, templates):
    parts = glyphs(frame, x, y, scale)
    if len(parts) == 1 and abs(parts[0][0] - round(18 * scale)) > 6 * scale:
        return None  # A visible half of a two-digit timer is not a whole timer.
    if len(parts) == 2 and (abs(parts[0][1] - parts[1][1]) > 3 * scale
                            or parts[1][0] - parts[0][0] > 15 * scale):
        return None
    if not 1 <= len(parts) <= 2:
        return None
    digits = [read_digit(glyph, templates) for glyph in parts]
    if None in digits or digits[0] == 0:
        return None
    value = int(''.join(str(digit) for digit in digits))
    return value if 1 <= value <= 90 else None


def learn(source, examples, scale):
    cap = cv2.VideoCapture(source)
    templates = {i: [] for i in range(10)}
    try:
        for timestamp, x, y, value in examples:
            cap.set(cv2.CAP_PROP_POS_MSEC, timestamp * 1000)
            ok, frame = cap.read()
            if not ok:
                raise ValueError(f'无法读取模板图标 {timestamp:.2f}s')
            parts = glyphs(frame, x, y, scale)
            for digit, part in zip(str(value), parts) if len(parts) == len(str(value)) else []:
                templates[int(digit)].append((part[2], part[3]))
    finally:
        cap.release()
    if not all(templates.values()):
        raise ValueError('模板中缺少可辨认的数字')
    return templates


def transitions(samples, start):
    changes = []
    history = []
    last_value = None
    last_read = None
    for time, observed in samples:
        history = (history + [(time, observed)])[-4:]
        count = Counter(value for _, value in history)
        if observed is None or count[observed] < 3:
            continue
        hit_time = next(t for t, value in history if value == observed)
        if last_read is None:
            code = 'opening' if hit_time - start < .42 else 'timer_start'
        elif hit_time - last_read > 1.25:
            elapsed = hit_time - last_read
            # Integer timers can be off by a tick. A return along the old timer
            # curve is an observation gap, not a new activation candidate.
            expected = last_value - elapsed
            code = 'timer_reacquired' if expected > 0 and abs(observed - expected) <= 1.5 else 'timer_start'
        elif observed >= last_value + 2:
            code = 'timer_restart'
        else:
            code = None
        if code and (observed >= 5 or code in ('opening', 'timer_reacquired')):
            changes.append(dict(time=round(hit_time, 3), value=observed, kind=code,
                                previous=last_value, lastRead=round(last_read, 3) if last_read is not None else None))
        last_value, last_read = observed, time
    for change in changes:
        time, value = change['time'], change['value']
        future = [digit for t, digit in samples if time + .35 <= t <= time + 1.25
                  and digit is not None]
        descending = sum(value - 2 <= digit < value for digit in future)
        change['countdownSupport'] = descending >= 3
    return changes


def scan(config, examples):
    source = config['source']
    scale = config['reference_size'][0] / 1280
    templates = learn(source, examples, scale)
    scans = {side: {slot: [] for slot in slots} for side, slots in config['dials'].items()}
    cap = cv2.VideoCapture(source)
    cap.set(cv2.CAP_PROP_POS_MSEC, config['start'] * 1000)
    next_sample = config['start']
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            time = cap.get(cv2.CAP_PROP_POS_MSEC) / 1000
            if time > config['end']:
                break
            if time < next_sample - .008:
                continue
            next_sample += .067
            for side, slots in config['dials'].items():
                for slot, (x, y) in slots.items():
                    value = timer(frame, x, y, scale, templates)
                    scans[side][slot].append((time, value))
    finally:
        cap.release()
    return sorted([dict(change, side=side, slot=slot) for side, slots in scans.items()
                   for slot, samples in slots.items()
                   for change in transitions(samples, config['start'])], key=lambda row: row['time'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--examples', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding='utf-8'))
    examples = json.loads(args.examples.read_text(encoding='utf-8'))
    args.output.write_text(json.dumps(scan(config, examples), ensure_ascii=False, indent=2),
                           encoding='utf-8')
