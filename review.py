"""Analyze a local Naruto Mobile replay and build a seekable browser report."""
from pathlib import Path
import argparse
import copy
import json
import shutil
import sys


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'engine'))

from analyse_color import DEFAULT, analyze
from cooldown_tracks import scan
from report_data import make_round


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def build(video, specs, output, auto_hud):
    rounds = []
    for number, options in enumerate(specs, 1):
        start, end = options['start'], options['end']
        if not 0 <= start < end:
            raise ValueError(f'第 {number} 回合起止时间无效')
        config = copy.deepcopy(DEFAULT)
        config.update(options.get('hud', {}), source=str(video), start=start, end=end)
        data = analyze(config, output / f'round-{number}', auto_hud=auto_hud)
        examples = options.get('timer_examples')
        timers = scan(data['config'], examples) if examples else []
        if examples:
            timer_path = output / f'round-{number}' / 'timers.json'
            timer_path.write_text(json.dumps(timers, ensure_ascii=False, indent=2), encoding='utf-8')
        rounds.append(make_round(data, options, number, timers))
    data_json = json.dumps(rounds, ensure_ascii=False, allow_nan=False)
    frontend = ROOT / 'frontend'
    for asset in frontend.iterdir():
        if asset.suffix in {'.js', '.css'}:
            shutil.copy2(asset, output)
    playback = output / 'replay.mp4'
    if video != playback:
        shutil.copy2(video, playback)
    (output / 'review-data.json').write_text(data_json, encoding='utf-8')
    template = (frontend / 'review-template.html').read_text(encoding='utf-8')
    (output / 'index.html').write_text(
        template.replace('__ROUNDS__', data_json.replace('<', '\\u003c')), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('video', type=Path, help='Local MP4 replay')
    parser.add_argument('--output', type=Path, default=Path('out'))
    ranges = parser.add_mutually_exclusive_group(required=True)
    ranges.add_argument('--round', type=float, nargs=2, metavar=('START', 'END'))
    ranges.add_argument('--rounds', type=Path, help='JSON with one or more rounds')
    parser.add_argument('--manual-hud', action='store_true',
                        help='Use the positions supplied by the profile instead of auto calibration')
    args = parser.parse_args()
    try:
        video = args.video.resolve(strict=True)
        if video.suffix.lower() != '.mp4':
            raise ValueError('请提供浏览器可播放的 MP4 录像')
        specs = read_json(args.rounds) if args.rounds else [
            dict(start=args.round[0], end=args.round[1])]
        if not isinstance(specs, list) or not specs:
            raise ValueError('需要至少一个回合')
        output = args.output.resolve()
        build(video, specs, output, not args.manual_hud)
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(2, f'{error}\n')
    print(output / 'index.html')


if __name__ == '__main__':
    main()
