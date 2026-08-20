from __future__ import annotations

from app.services.tsp import (
    build_haversine_matrix,
    nearest_neighbor_tour,
    optimize_round_trip,
    path_length,
    two_opt,
)


def test_haversine_symmetric():
    points = [(49.29, 6.53), (49.12, 6.18), (49.19, 6.90)]
    matrix = build_haversine_matrix(points)
    assert matrix[0][1] == matrix[1][0]
    assert matrix[0][0] == 0


def test_two_opt_improves_or_equals():
    points = [
        (49.29, 6.53),
        (49.35, 6.70),
        (49.20, 6.40),
        (49.10, 6.90),
        (49.40, 6.20),
    ]
    matrix = build_haversine_matrix(points)
    nn = nearest_neighbor_tour(matrix, start=0)
    improved = two_opt(nn, matrix)
    assert path_length(improved, matrix, round_trip=False) <= path_length(
        nn, matrix, round_trip=False
    ) + 1e-6


def test_round_trip_starts_at_depot():
    points = [(49.29, 6.53), (49.12, 6.18), (49.19, 6.90), (49.25, 6.60)]
    matrix = build_haversine_matrix(points)
    order = optimize_round_trip(matrix, start=0)
    assert order[0] == 0
    assert sorted(order) == list(range(len(points)))
