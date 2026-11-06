#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""星尘港湾 · 战斗机制参考模型（Python 版）

这个文件不是游戏运行时的一部分，也不参与构建。
它把 index.html 里的数值与公式**逐条抄出来**，方便直接阅读、调整与验算：

    python3 py/combat_model.py

改这里的数字不会影响游戏；确认手感后，按同样的值去改 index.html 即可。
对应关系写在每个函数上方（形如  index.html: fireBolt）。

设计原则（三主题各有性格）
    极光青  ION BURST     —— 速度就是射速：飞得越快，弹幕越密
    绯红脉冲 PHASE RAM     —— 加速后直接撞上去：接触即秒杀，撞击反哺速度
    琥珀星火 BROOD CARRIER —— 自己不开火，放出小战舰替你打

所有主题都是"无敌"的：没有血量、不会失败，只有分数和武器等级。
"""

from dataclasses import dataclass, field
from math import exp, hypot, cos, sin, pi

# ---------------------------------------------------------------- 全局数值

BASE_MAX_SPEED = 780.0     # 基础最高速度 px/s（index.html: MAXSP）
BASE_DAMP = 1.35           # 基础阻尼 1/s
THRUST_ACCEL = 980.0       # 推进加速度 px/s^2

# 分数 -> 武器等级 1..5（index.html: LEVELS）
LEVELS = (0, 800, 2200, 4200, 7000)

# 冲撞机制（index.html: RAM_MIN / updateRam / ramSmash）
RAM_MIN_SPEED = 300.0      # 达到这个速度才"武装"，才能撞碎敌机
RAM_MAGNET_RANGE = 170.0   # 冲撞磁吸半径
RAM_MAGNET_PULL = 210.0    # 磁吸速度 px/s
RAM_BASE_REACH = 30.0      # 命中判定 = 敌机半径 + 这个值
RAM_REACH_BONUS = 18.0     # 速度越快判定越宽（最多再 +18）
RAM_COOLDOWN = 0.1         # 两次撞击之间的最短间隔 s
RAM_KICK = 70.0            # 撞击后沿原方向补的速度 px/s


@dataclass(frozen=True)
class Mob:
    """小怪（index.html: MOBS）"""
    key: str
    hp: int
    radius: float
    speed: float
    score: int


MOBS = {
    "drifter": Mob("drifter", hp=3, radius=16, speed=205, score=60),
    "prism":   Mob("prism",   hp=4, radius=18, speed=175, score=80),
    "swarm":   Mob("swarm",   hp=1, radius=10, speed=262, score=30),
}


@dataclass(frozen=True)
class Theme:
    """主题：配色 + 飞行手感 + 武器 + 敌人（index.html: PALETTES）"""
    key: str
    name_zh: str
    name_en: str
    weapon: str
    mob: str
    speed_mul: float     # 最高速度倍率
    damp: float          # 阻尼 1/s，越小越"滑"
    scale: float         # 船体绘制缩放（琥珀是航母，画得更大）


THEMES = (
    Theme("aurora", "极光青", "AURORA CYAN", "bolt", "drifter", 1.00, 1.35, 1.18),
    Theme("pulse", "绯红脉冲", "CRIMSON PULSE", "ram", "prism", 1.14, 1.12, 1.08),
    Theme("ember", "琥珀星火", "AMBER EMBER", "carrier", "swarm", 0.70, 1.56, 1.82),
)

# ---------------------------------------------------------------- 通用公式


def max_speed(theme: Theme) -> float:
    """主题下的最高速度（index.html: MAXSP = 780 * palette.spd）"""
    return BASE_MAX_SPEED * theme.speed_mul


def weapon_level(score: int) -> int:
    """分数换算武器等级 1..5（index.html: weaponLevelFor）"""
    lv = 1
    for i, need in enumerate(LEVELS, start=1):
        if score >= need:
            lv = i
    return lv


def level_progress(score: int):
    """当前等级与下一级还差多少分，用于 UI 进度提示。"""
    lv = weapon_level(score)
    if lv >= len(LEVELS):
        return lv, 0
    return lv, LEVELS[lv] - score


def step_velocity(vx: float, vy: float, ax: float, ay: float,
                  theme: Theme, dt: float) -> tuple:
    """一帧的惯性滑翔（index.html: update() 的速度积分）

    松开鼠标时 ax=ay=0，速度只会被指数阻尼吃掉 —— 这就是"滑行"手感。
    用 exp() 而不是线性衰减，保证不同帧率下衰减一致。
    """
    vx += ax * dt
    vy += ay * dt
    decay = exp(-theme.damp * dt)
    vx *= decay
    vy *= decay
    cap = max_speed(theme)
    sp = hypot(vx, vy)
    if sp > cap:
        vx *= cap / sp
        vy *= cap / sp
    return vx, vy


def terminal_speed(theme: Theme) -> float:
    """持续满推力时能到达的速度（受阻尼与上限共同约束）。"""
    return min(max_speed(theme), THRUST_ACCEL / theme.damp)


# ---------------------------------------------------------------- 极光青：离子脉冲


def bolt_interval(lv: int, speed: float) -> float:
    """开火间隔：等级越高越快，速度越快也越快（index.html: fireBolt）

    满速冲刺时约比静止快 1.5 倍 —— 这就是"速度即射速"。
    """
    return max(0.09, (0.36 - (lv - 1) * 0.03) / (1 + speed / 1500.0))


def bolt_count(lv: int) -> int:
    """一次齐射的弹数：LV3 起 2 发，LV5 起 3 发。"""
    if lv >= 5:
        return 3
    if lv >= 3:
        return 2
    return 1


def bolt_damage(lv: int) -> int:
    return 2 + (lv - 1) // 2


def bolt_dps(lv: int, speed: float) -> float:
    """理论每秒伤害（假设全部命中）。"""
    return bolt_count(lv) * bolt_damage(lv) / bolt_interval(lv, speed)


# ---------------------------------------------------------------- 绯红脉冲：相位冲撞


def ram_armed(speed: float) -> bool:
    """速度够快才武装，HUD 会显示"冲撞就绪"。"""
    return speed >= RAM_MIN_SPEED


def ram_reach(mob: Mob, speed: float) -> float:
    """命中判定半径：速度越快，能量刃越长。"""
    reach = RAM_BASE_REACH + RAM_REACH_BONUS * (1 - min(1.0, RAM_MIN_SPEED / max(speed, 1)))
    return mob.radius + reach


def ram_bonus(mob: Mob, speed: float) -> int:
    """撞击的额外得分：高速撞击（>600）翻倍。"""
    return round(mob.score * (1.2 if speed > 600 else 0.6))


def ram_kills_per_second(speed: float, drones_in_reach: float = 1.0) -> float:
    """粗略估算：武装状态下每秒最多撞掉几架（受冷却限制）。"""
    if not ram_armed(speed):
        return 0.0
    return drones_in_reach / RAM_COOLDOWN


# ---------------------------------------------------------------- 琥珀星火：蜂群航母


def drone_count(lv: int) -> int:
    """常驻小战舰数量（index.html: spawnDrone / maxD）"""
    return 2 + int(lv * 0.9)


def drone_interval(lv: int) -> float:
    """小战舰开火间隔。"""
    return max(0.38, 0.8 - (lv - 1) * 0.07)


def drone_damage(lv: int = 1) -> int:
    """小战舰子弹伤害固定 1（等级只增加数量与射速）。"""
    return 1


def carrier_dps(lv: int) -> float:
    return drone_count(lv) * drone_damage() / drone_interval(lv)


def enemy_target(theme: Theme, sector: int) -> int:
    """屏幕外的敌机补足到多少架（index.html: enemyTarget）

    冲撞主题刻意更稀疏：路上拦路的敌机少，撞到一次才更值钱。
    """
    base = min(11, 5 + int(sector * 0.8))
    if theme.weapon == "ram":
        return max(2, base - 3)
    return base


# ---------------------------------------------------------------- 太空堡垒
FORT_R = 92            # 半径
FORT_HP = 150          # 基础血量，每进一个星区 +40
FORT_SCORE = 2000      # 摧毁奖励
FORT_SPAWN_RANGE = (3000, 5600)   # 出生半径：永远在视野外，很难撞见
FORT_RESPAWN = 9.0     # 摧毁后多久在别处重生
FORT_LAUNCH = (2.6, 5.4)          # 放敌机的间隔（随星区缩短）

NAV_STEP = 300         # 每 300 分算一个「积分等级」
NAV_EVERY = 10         # 每 10 个等级给一次坐标指引
NAV_PING = 12.0        # 一次指引持续多少秒

PRISM_SPLIT_GEN = 3    # 棱镜最多分裂 3 代
PRISM_SPLIT_CAP = 12   # 场上敌机超过这个数就不再分裂


def fort_hp(sector: int) -> int:
    return FORT_HP + (sector - 1) * 40


def nav_ping_score(rank_multiple: int = NAV_EVERY) -> int:
    """第 n 次坐标指引需要多少分。"""
    return rank_multiple * NAV_STEP


# ---------------------------------------------------------------- 飞行手感


def flight_profile(theme: Theme, seconds: float = 6.0, dt: float = 1 / 60):
    """按住推进 seconds 秒，然后松开 coast 秒：返回 (速度曲线, 松手滑行距离)。

    用来直观看三主题的性格差异 —— 红主题上限更高、更"滑"。
    """
    vx, vy = 0.0, 0.0
    ax = THRUST_ACCEL
    t_top = None
    dt_step = dt
    steps = int(seconds / dt_step)
    for i in range(steps):
        vx, vy = step_velocity(vx, vy, ax, 0.0, theme, dt_step)
        if t_top is None and hypot(vx, vy) >= terminal_speed(theme) * 0.98:
            t_top = i * dt_step
    v_release = hypot(vx, vy)

    # 松手后的惯性滑行距离（对 exp 衰减积分：∫v dt = v/damp）
    coast = v_release / theme.damp
    return v_release, (t_top if t_top is not None else float("inf")), coast


# ---------------------------------------------------------------- 报告


def report() -> None:
    line = "─" * 72
    print("星尘港湾 · 战斗机制参考模型")
    print(line)

    print("\n[主题与飞行手感]  满推力 %.0f px/s²" % THRUST_ACCEL)
    print(f"{'主题':<8}{'最高速':>8}{'终端速':>8}{'到速用时':>10}{'松手滑行':>10}")
    for th in THEMES:
        v, t_top, coast = flight_profile(th)
        t_top_s = "—" if t_top == float("inf") else f"{t_top:.2f}s"
        print(f"{th.name_zh:<8}{max_speed(th):>8.0f}{terminal_speed(th):>8.0f}"
              f"{t_top_s:>10}{coast:>9.0f}px")

    print("\n" + line)
    print("[极光青 · 离子脉冲]  DPS 随速度提升")
    print(f"{'LV':<4}{'弹数':>5}{'单击伤害':>9}{'静止间隔':>10}{'满速间隔':>10}{'满速DPS':>10}")
    sp_max = max_speed(THEMES[0])
    for lv in range(1, 6):
        print(f"{lv:<4}{bolt_count(lv):>5}{bolt_damage(lv):>9}"
              f"{bolt_interval(lv, 0):>9.2f}s{bolt_interval(lv, sp_max):>9.2f}s"
              f"{bolt_dps(lv, sp_max):>9.1f}")

    print("\n" + line)
    print("[绯红脉冲 · 相位冲撞]  武装阈值 %.0f px/s，冷却 %.2fs" % (RAM_MIN_SPEED, RAM_COOLDOWN))
    mob = MOBS[THEMES[1].mob]
    print(f"{'速度':>8}{'武装':>6}{'判定半径':>10}{'撞击得分':>10}{'撞 1 架需':>10}")
    for sp in (250, 300, 400, 500, 600, 700, 800):
        armed = "是" if ram_armed(sp) else "否"
        reach = ram_reach(mob, sp)
        bonus = ram_bonus(mob, sp)
        print(f"{sp:>8}{armed:>6}{reach:>10.0f}{bonus:>10}{RAM_COOLDOWN:>9.2f}s")
    print("  提示：撞击瞬间还会 +%.0f px/s 的动量，越撞越快。" % RAM_KICK)

    print("\n" + line)
    print("[琥珀星火 · 蜂群航母]")
    print(f"{'LV':<4}{'小战舰':>7}{'单击伤害':>9}{'间隔':>8}{'DPS':>9}")
    for lv in range(1, 6):
        print(f"{lv:<4}{drone_count(lv):>7}{drone_damage():>9}"
              f"{drone_interval(lv):>7.2f}s{carrier_dps(lv):>9.1f}")

    print("\n" + line)
    print("\n" + line)
    print("[敌机密度]  每星区屏幕外补足架数")
    print(f"{'主题':<8}{'第 1 星区':>10}{'第 2 星区':>10}{'第 3 星区':>10}{'第 5 星区':>10}")
    for th in THEMES:
        row = "".join(f"{enemy_target(th, sec):>10}" for sec in (1, 2, 3, 5))
        print(f"{th.name_zh:<8}{row}")

    print("\n" + line)
    print("[太空堡垒]  敌机生成点")
    print(f"{'星区':<8}" + "".join(f"{s:>10}" for s in (1, 2, 3, 5)))
    print(f"{'血量':<8}" + "".join(f"{fort_hp(s):>10}" for s in (1, 2, 3, 5)))
    print(f"摧毁奖励 {FORT_SCORE} 分 · 出生距离 {FORT_SPAWN_RANGE[0]}~{FORT_SPAWN_RANGE[1]}px"
          f" · {FORT_RESPAWN:.0f}s 后换地方重生")
    print(f"导航：每 {NAV_STEP} 分升一级，每 {NAV_EVERY} 级（{nav_ping_score()} 分）给一次 "
          f"{NAV_PING:.0f}s 坐标指引")

    print("\n" + line)
    print(f"[棱镜分裂]  最多 {PRISM_SPLIT_GEN} 代，场上超过 {PRISM_SPLIT_CAP} 架就不再分裂")
    count, gen = 1, 0
    while gen < PRISM_SPLIT_GEN:
        gen += 1
        count *= 2
        hp = max(1, 4 - gen)
        print(f"  第 {gen} 代：{count} 架 · 每架 {hp} HP · 单架 {max(10, round(80 * 0.55 ** gen))} 分")
    print(f"  一条血缘最多 {count} 架，全部打完就彻底结束")

    print("\n[武器等级门槛]")
    for i, need in enumerate(LEVELS, start=1):
        print(f"  LV.{i}  >= {need:>5} 分")
    print("\n提示：分数来源 星尘 +10 / 穿环 +50 / 击落小怪 +30~80 / 点亮星区 +500")


if __name__ == "__main__":
    report()
