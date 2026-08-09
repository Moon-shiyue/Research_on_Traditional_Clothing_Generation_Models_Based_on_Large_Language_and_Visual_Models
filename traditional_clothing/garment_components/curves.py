"""
curves - 二维曲线生成工具

为传统服饰样板提供线段、贝塞尔曲线、圆弧等基本曲线原语，
输出离散化的 Point2D 点列表，用于定义面板轮廓及缝边。
"""

from __future__ import annotations

import math
from typing import List, Optional

from .base import Point2D


def line(start: Point2D, end: Point2D, num_points: int = 0) -> List[Point2D]:
    """生成从 start 到 end 的直线段。

    Args:
        start: 起点
        end: 终点
        num_points: 中间插值点数（不含两端）。为 0 时只返回两端点。

    Returns:
        点列表，包含起点、中间插值点、终点。
    """
    if num_points <= 0:
        return [start, end]
    points = [start]
    for i in range(1, num_points + 1):
        t = i / (num_points + 1)
        points.append(Point2D(
            start.x + t * (end.x - start.x),
            start.y + t * (end.y - start.y),
        ))
    points.append(end)
    return points


def bezier_curve(
    control_points: List[Point2D],
    num_points: int = 50,
) -> List[Point2D]:
    """生成任意阶贝塞尔曲线。

    使用 de Casteljau 算法递归求值。

    Args:
        control_points: 控制点列表，至少 2 个点。
        num_points: 输出点数（含两端）。

    Returns:
        贝塞尔曲线上的均匀采样点列表。
    """
    if len(control_points) < 2:
        return list(control_points)
    if num_points < 2:
        num_points = 2
    result: List[Point2D] = []
    for i in range(num_points):
        t = i / (num_points - 1)
        result.append(_de_casteljau(control_points, t))
    return result


def _de_casteljau(pts: List[Point2D], t: float) -> Point2D:
    """de Casteljau 递推求值。"""
    temp = [Point2D(p.x, p.y) for p in pts]
    n = len(temp)
    for r in range(1, n):
        for i in range(n - r):
            temp[i] = Point2D(
                (1 - t) * temp[i].x + t * temp[i + 1].x,
                (1 - t) * temp[i].y + t * temp[i + 1].y,
            )
    return temp[0]


def arc(
    center: Point2D,
    radius: float,
    start_angle_rad: float,
    end_angle_rad: float,
    num_points: int = 50,
    clockwise: bool = False,
) -> List[Point2D]:
    """生成圆弧。

    圆弧从 start_angle_rad 扫掠到 end_angle_rad。

    Args:
        center: 圆心
        radius: 半径（厘米）
        start_angle_rad: 起始角度（弧度），0 为 +x 方向，逆时针为正
        end_angle_rad: 终止角度（弧度）
        num_points: 输出点数（含两端）
        clockwise: 是否顺时针方向

    Returns:
        圆弧上的均匀采样点列表。
    """
    if num_points < 2:
        num_points = 2
    if radius <= 0:
        return [center] * num_points

    # 归一化角度范围
    sa = start_angle_rad
    ea = end_angle_rad
    if clockwise:
        # 保证从 sa 顺时针到 ea
        while ea > sa:
            ea -= 2 * math.pi
        span = ea - sa  # 负值
    else:
        while ea < sa:
            ea += 2 * math.pi
        span = ea - sa  # 正值

    points: List[Point2D] = []
    for i in range(num_points):
        t = i / (num_points - 1)
        angle = sa + t * span
        points.append(Point2D(
            center.x + radius * math.cos(angle),
            center.y + radius * math.sin(angle),
        ))
    return points


def arc_by_sweep(
    center: Point2D,
    radius: float,
    start_angle_rad: float,
    sweep_angle_rad: float,
    num_points: int = 50,
) -> List[Point2D]:
    """以扫掠角生成圆弧的便捷方法。

    Args:
        sweep_angle_rad: 扫掠角（弧度），正为逆时针，负为顺时针
    """
    return arc(
        center, radius, start_angle_rad, start_angle_rad + sweep_angle_rad,
        num_points=num_points,
        clockwise=(sweep_angle_rad < 0),
    )


def circle(center: Point2D, radius: float, num_points: int = 100) -> List[Point2D]:
    """生成完整圆（闭合多边形逼近）。"""
    pts = arc(center, radius, 0, 2 * math.pi, num_points)
    # 移除最后一个点（与第一个重合）
    return pts[:-1]


def cloud_scallop(
    base_start: Point2D,
    base_end: Point2D,
    bulge_height: float,
    bulge_ratio: float = 0.4,
    num_points: int = 30,
) -> List[Point2D]:
    """生成云纹波浪边（单个扇贝形凸起）。

    在 base_start 和 base_end 之间生成一段向上凸起的弧线，
    控制点使曲线呈现"云朵花瓣"的圆润形态。

    Args:
        base_start: 波浪起点
        base_end: 波浪终点
        bulge_height: 凸起高度（厘米），正值向外凸
        bulge_ratio: 凸起峰值位置比例（0~1），默认 0.4 使左右不对称（云纹特征）
        num_points: 输出点数

    Returns:
        波浪弧线的采样点列表。
    """
    # 弦中点
    mid = Point2D(
        (base_start.x + base_end.x) / 2,
        (base_start.y + base_end.y) / 2,
    )
    # 弦的方向向量
    dx = base_end.x - base_start.x
    dy = base_end.y - base_start.y
    chord_len = math.hypot(dx, dy)
    if chord_len < 1e-6:
        return [base_start, base_end]
    # 法向量（左侧法向）
    nx = -dy / chord_len
    ny = dx / chord_len

    # 峰值点：沿弦方向偏移 bulge_ratio，沿法向偏移 bulge_height
    peak = Point2D(
        base_start.x + bulge_ratio * dx + bulge_height * nx,
        base_start.y + bulge_ratio * dy + bulge_height * ny,
    )

    # 使用三个控制点的二次贝塞尔：起点、峰值偏置、终点
    # 第一控制点：从起点出发沿法向
    cp1 = Point2D(
        base_start.x + bulge_height * 0.5 * nx,
        base_start.y + bulge_height * 0.5 * ny,
    )
    cp2 = Point2D(
        base_end.x + bulge_height * 0.5 * nx,
        base_end.y + bulge_height * 0.5 * ny,
    )

    return bezier_curve([base_start, cp1, peak, cp2, base_end], num_points)
