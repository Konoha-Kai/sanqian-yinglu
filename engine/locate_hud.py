"""Locate the replay's health bars and skill slots without a recognition model."""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np


def sample_hud(config):
    cap = cv2.VideoCapture(config['source'])
    frames = []
    use_until = min(config['end'], config['start'] + 2.3)
    try:
        for time in np.linspace(max(0, config['start'] - .15), use_until, 16):
            cap.set(cv2.CAP_PROP_POS_MSEC, time * 1000)
            ok, frame = cap.read()
            if ok:
                height, width = frame.shape[:2]
                frames.append(frame[:round(height * .30)])
    finally:
        cap.release()
    if len(frames) < 5:
        raise ValueError('至少需要五张可解码的 HUD 样本')
    return np.stack(frames), width, height


def bar_span(row, minimum):
    columns = np.flatnonzero(row)
    runs = np.split(columns, np.flatnonzero(np.diff(columns) > 3) + 1)
    longest = max(runs, key=len)
    if len(longest) < minimum:
        return None
    return int(longest[0]), int(longest[-1]) + 1


def health_regions(frames, width, height, config):
    hsv = np.stack([cv2.cvtColor(frame[:round(height * .105)], cv2.COLOR_BGR2HSV)
                    for frame in frames])
    hue, sat, value = np.moveaxis(hsv, -1, 0)
    warm = ((hue <= config['hp_hue_max']) | (hue >= 174))
    warm &= (sat >= config['hp_saturation_min']) & (value >= config['hp_value_min'])
    presence = warm.mean(axis=0) >= .22
    regions = {}
    for side, (left, right) in {'A': (.105, .267), 'B': (.711, .876)}.items():
        x0, x1 = round(width * left), round(width * right)
        candidates = []
        for y in range(round(height * .039), presence.shape[0]):
            span = bar_span(presence[y, x0:x1], round(width * .095))
            if span:
                candidates.append((y, *span))
        if not candidates:
            raise ValueError(f'{side} 侧找不到可验证的红橙血条。请选择开局、双方血条可见的区间。')
        largest = max(right - left for _, left, right in candidates)
        band_rows = [row for row in candidates if row[2] - row[1] >= largest * .87]
        bands = np.split(np.array(band_rows), np.flatnonzero(np.diff([row[0] for row in band_rows]) > 1) + 1)
        band = max(bands, key=len)
        if len(band) < max(2, round(height * .004)):
            raise ValueError(f'{side} 侧血条色带过窄，无法稳定测量')
        regions[side] = [round(x0 + np.median(band[:, 1])), int(band[0, 0]),
                         round(x0 + np.median(band[:, 2])), int(band[-1, 0]) + 1]
    spans = [box[2] - box[0] for box in regions.values()]
    if min(spans) / max(spans) < .83:
        raise ValueError('两侧可见血条宽度不一致，请在掉血前校准')
    return regions


def skill_regions(still, width, height, slot_layout):
    scale = width / 1280
    gray = cv2.cvtColor(still, cv2.COLOR_BGR2GRAY)
    circles = cv2.HoughCircles(cv2.GaussianBlur(gray, (5, 5), 0), cv2.HOUGH_GRADIENT,
                              1, 44 * scale, param1=114, param2=20,
                              minRadius=round(20 * scale), maxRadius=round(40 * scale))
    if circles is None:
        raise ValueError('找不到技能圆框')
    dials = {}
    for side, (left, right) in {'A': (.11, .425), 'B': (.565, .88)}.items():
        row = sorted((float(x), float(y)) for x, y, _ in circles[0]
                     if width * left < x < width * right and height * .171 < y < height * .255)
        groups = [row[i:i + 6] for i in range(len(row) - 5)]
        best = None
        for group in groups:
            x, y = np.array(group).T
            spacing, start = np.polyfit(np.arange(6), x, 1)
            fitted = start + spacing * np.arange(6)
            deviation = float(np.max(np.abs(x - fitted)))
            if not 54 * scale <= spacing <= 74 * scale or deviation > 10 * scale or np.ptp(y) > 16 * scale:
                continue
            if best is None or deviation < best[0]:
                best = (deviation, fitted, float(np.median(y)))
        if best is None:
            raise ValueError(f'{side} 侧找不到六个稳定且相邻的技能圆框')
        _, positions, y = best
        # Read left-to-right and retain roster-specific slot names from the layout.
        slots = sorted(slot_layout[side], key=lambda slot: slot_layout[side][slot][0])
        dials[side] = {slot: [round(x), round(y)] for slot, x in zip(slots, positions)}
    return dials


def locate(config):
    frames, width, height = sample_hud(config)
    still = np.median(frames, axis=0).astype('uint8')
    bars = health_regions(frames, width, height, config)
    slots = skill_regions(still, width, height, config['dials'])
    return dict(config, hp=bars, dials=slots, reference_size=[width, height],
                radius=max(8, round(width * 18 / 1280))), still


def main():
    from analyse_color import DEFAULT

    parser = argparse.ArgumentParser(description='Find health bars and dial centers in replay footage.')
    parser.add_argument('video', type=Path)
    parser.add_argument('--start', required=True, type=float)
    parser.add_argument('--end', required=True, type=float)
    parser.add_argument('--layout', type=Path, help='Optional config defining slot names and color thresholds')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--overlay', type=Path)
    args = parser.parse_args()
    layout = json.loads(args.layout.read_text(encoding='utf-8')) if args.layout else DEFAULT
    config, still = locate(dict(layout, source=str(args.video.resolve(strict=True)),
                               start=args.start, end=args.end))
    args.output.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
    if args.overlay:
        for side in 'AB':
            x0, y0, x1, y1 = config['hp'][side]
            cv2.rectangle(still, (x0, y0), (x1 - 1, y1 - 1), (100, 245, 115), 1)
            for x, y in config['dials'][side].values():
                cv2.circle(still, (x, y), config['radius'], (255, 210, 90), 1)
                cv2.drawMarker(still, (x, y), (255, 210, 90), cv2.MARKER_CROSS, 7, 1)
        ok, encoded = cv2.imencode(args.overlay.suffix, still)
        if not ok:
            raise ValueError('无法编码预览图')
        args.overlay.write_bytes(encoded.tobytes())


if __name__ == '__main__':
    main()
