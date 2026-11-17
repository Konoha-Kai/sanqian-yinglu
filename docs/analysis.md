# 使用与判定说明

## 判定代码

| 模块 | 输入与输出 |
| --- | --- |
| [locate_hud.py](../engine/locate_hud.py) | 用顶部红橙长条和成排圆框定位两边的血条与技能槽；特殊忍者的槽位顺序来自配置。 |
| [analyse_color.py](../engine/analyse_color.py) | 读取固定区域，按时间记录颜色状态、掉血和遮挡等读数异常。血量是可见填充比例。 |
| [cooldown_tracks.py](../engine/cooldown_tracks.py) | 根据当前录像确认过的数字样本追踪倒计时，区分开局已有读数、旧读数恢复及读数上跳。上跳可能是强化或刷新，也可能是再释放。 |
| [refine_onsets.py](../engine/refine_onsets.py) | 合并临近掉血段，必要时回查原始帧定位血条开始变化的时点。 |
| [attribute_resources.py](../engine/attribute_resources.py) 和 [judge_combat.py](../engine/judge_combat.py) | 在掉血附近回查双方资源变化，同时保留可能的连招补段、互换和来源不明的伤害。 |
| [exchange_verdict.py](../engine/exchange_verdict.py) 和 [report_data.py](../engine/report_data.py) | 将机器观察及复核分开保存，给每次动作分别记录释放、命中、位移、控制、打断、伤害和起手。由此生成前端所需数据。 |

状态图标只做证据，确认录像里的动作时保留来源。前摇换位和后摇换位可属于一次技能释放。明确刷新后再出招时，单独记再次释放。无伤害位移和被躲开的技能都可以成立；有掉血也可能出现霸体扛招或后段打断。

## 前端

[review-template.html](../frontend/review-template.html) 提供回放和回合切换。[review-layers.js](../frontend/review-layers.js) 画出技能与血量时间轴。[review-tree.js](../frontend/review-tree.js) 绘制双列博弈树，每个节点和录像共用同一时间基准。没有独立回放证据时，自动树里的连接表示时间顺序。经复核的实战走法和备选分支可由回合配置提供。

## 回合配置

```sh
python review.py replay.mp4 --rounds rounds.json --output out
```

`rounds.json` 是一个回合数组。时间单位是原视频秒数，A 是左方，B 是右方。下面是配置写法示例。

```json
[
  {
    "start": 8.7,
    "end": 42.95,
    "label": "第一回合",
    "players": {"A": "侠隐江湖佐助", "B": "秽土水门"}
  },
  {
    "start": 56.5,
    "end": 101.2,
    "label": "第二回合",
    "players": {"A": "九喇嘛连结鸣人", "B": "秽土水门"}
  }
]
```

可选字段：

- `hud` 覆盖 [默认布局](../engine/analyse_color.py) 中的定位配置。自动定位仍使用 `dials` 的左右顺序给槽位命名。遇到特殊忍者请提供实际的槽位顺序。自动定位失败时，可以用 `--manual-hud` 与明确的 `hp`、`dials`、`reference_size` 一起运行。
- `timer_examples` 是已经人工读清的黄色倒计时样本，每项是 `[秒数, 槽位中心X, 槽位中心Y, 数字]`。用于匹配同一录像字体，至少覆盖 0–9。省略时继续使用颜色观察。
- `actions` 是人工或定点回放已经核对的事件。每项含 `time`、`side`、`slot`、`title`、`result`、`origin`，可选 `end`、`phases` 和 `facts`。例如 `facts` 可记录 `{"contact":"未命中","movement":"对手换位躲开"}`。
- `trees` 可提供已经复核的博弈树。每段含 `time`、`short`、`context`、`path`、`outcome`，可选 `alternative` 和 `fork`。步骤含 `side`、`label`、`title`、`text` 与可选 `time`。结果可省略 `side`。分叉位置 `0` 是局面入口，`1` 是第一个动作。省略时根据 HUD 生成待核的交手线索。

报告目录包含本地回放副本、页面资源、原始测量与证据图。默认 `out/` 已被 Git 忽略。
