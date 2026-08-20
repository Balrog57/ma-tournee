from __future__ import annotations

import math
from typing import Sequence


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius = 6_371_000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius * math.asin(math.sqrt(a))


def build_haversine_matrix(points: Sequence[tuple[float, float]]) -> list[list[float]]:
    n = len(points)
    matrix = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(i + 1, n):
            d = haversine_m(points[i][0], points[i][1], points[j][0], points[j][1])
            matrix[i][j] = d
            matrix[j][i] = d
    return matrix


def nearest_neighbor_tour(matrix: list[list[float]], start: int = 0) -> list[int]:
    n = len(matrix)
    if n == 0:
        return []
    if n == 1:
        return [0]
    unvisited = set(range(n))
    unvisited.remove(start)
    tour = [start]
    current = start
    while unvisited:
        nxt = min(unvisited, key=lambda j: matrix[current][j])
        tour.append(nxt)
        unvisited.remove(nxt)
        current = nxt
    return tour


def two_opt(tour: list[int], matrix: list[list[float]]) -> list[int]:
    if len(tour) < 4:
        return tour

    def length(path: list[int]) -> float:
        total = 0.0
        for i in range(len(path) - 1):
            total += matrix[path[i]][path[i + 1]]
        return total

    improved = True
    best = tour[:]
    while improved:
        improved = False
        for i in range(1, len(best) - 2):
            for j in range(i + 1, len(best) - 1):
                if j - i == 1:
                    continue
                candidate = best[:i] + best[i : j + 1][::-1] + best[j + 1 :]
                if length(candidate) + 1e-9 < length(best):
                    best = candidate
                    improved = True
    return best


def optimize_open_tour(matrix: list[list[float]], start: int = 0) -> list[int]:
    """Open tour starting at depot index (no forced return)."""
    nn = nearest_neighbor_tour(matrix, start=start)
    return two_opt(nn, matrix)


def optimize_round_trip(matrix: list[list[float]], start: int = 0) -> list[int]:
    """Round trip: order of visits starting and ending at depot conceptually.

    Returns open order of all points starting at depot; caller appends depot for geometry.
    """
    n = len(matrix)
    if n <= 1:
        return list(range(n))

    # Work on a closed tour then drop the final return for ordering of unique stops
    nn = nearest_neighbor_tour(matrix, start=start)
    closed = nn + [start]
    # 2-opt on closed path representation (indices without duplicate end for mutation)
    order = nn[:]
    improved = True

    def closed_length(path: list[int]) -> float:
        total = 0.0
        for i in range(len(path) - 1):
            total += matrix[path[i]][path[i + 1]]
        total += matrix[path[-1]][path[0]]
        return total

    while improved:
        improved = False
        best_len = closed_length(order)
        for i in range(1, n - 1):
            for j in range(i + 1, n):
                candidate = order[:i] + order[i:j][::-1] + order[j:]
                new_len = closed_length(candidate)
                if new_len + 1e-9 < best_len:
                    order = candidate
                    best_len = new_len
                    improved = True
    # Rotate so depot is first
    if start in order:
        idx = order.index(start)
        order = order[idx:] + order[:idx]
    return order


def path_length(order: list[int], matrix: list[list[float]], round_trip: bool) -> float:
    if not order:
        return 0.0
    total = 0.0
    for i in range(len(order) - 1):
        total += matrix[order[i]][order[i + 1]]
    if round_trip and len(order) > 1:
        total += matrix[order[-1]][order[0]]
    return total
