"""
    Filename: wiring.py
    Description:
        Builds wire routes with real bend arcs. A route is a start and end terminal plus
        waypoints. Every corner becomes an arc at the cable's minimum bend radius, and any
        corner without room for that radius is reported.
"""

import math


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def add(a, b, k=1.0):
    return (a[0] + b[0] * k, a[1] + b[1] * k, a[2] + b[2] * k)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def unit(a):
    n = length(a) or 1.0
    return (a[0] / n, a[1] / n, a[2] / n)


def fillet_path(points, radius, step=4.0):
    """Rounds a polyline. Returns (samples, smallest radius reached, bend count)."""
    pts = [points[0]]
    for q in points[1:]:
        if length(sub(q, pts[-1])) > 0.05:
            pts.append(q)
    corners = {}
    for i in range(1, len(pts) - 1):
        u, v = unit(sub(pts[i - 1], pts[i])), unit(sub(pts[i + 1], pts[i]))
        between = math.acos(max(-1, min(1, dot(u, v))))
        turn = math.pi - between
        if turn > math.radians(4):
            corners[i] = {"half": turn / 2, "trim": radius * math.tan(turn / 2)}
    # Corners sharing a segment split its length, so radii shrink only where room runs out.
    for _ in range(4):
        for i in range(len(pts) - 1):
            a, b = corners.get(i), corners.get(i + 1)
            room = length(sub(pts[i + 1], pts[i]))
            used = (a["trim"] if a else 0) + (b["trim"] if b else 0)
            if used > room:
                k = room / used
                if a:
                    a["trim"] *= k
                if b:
                    b["trim"] *= k
    samples = [pts[0]]
    smallest = None
    for i in range(1, len(pts)):
        end = pts[i]
        corner = corners.get(i)
        start = samples[-1]
        target = add(end, unit(sub(start, end)), corner["trim"]) if corner else end
        run = length(sub(target, start))
        n = max(1, int(run // step))
        for k in range(1, n + 1):
            samples.append(add(start, sub(target, start), k / n))
        if corner:
            r = corner["trim"] / math.tan(corner["half"])
            smallest = r if smallest is None else min(smallest, r)
            u, v = unit(sub(pts[i - 1], end)), unit(sub(pts[i + 1], end))
            centre_dir = unit(add(u, v))
            centre = add(end, centre_dir, r / math.cos(corner["half"]))
            a0, a1 = sub(samples[-1], centre), sub(add(end, v, corner["trim"]), centre)
            angle = math.acos(max(-1, min(1, dot(unit(a0), unit(a1)))))
            axis = unit(cross(a0, a1))
            n = max(4, int(angle * r / 1.2))
            for k in range(1, n + 1):
                t = angle * k / n
                rotated = add(add(tuple(c * math.cos(t) for c in a0), cross(axis, a0), math.sin(t)),
                              axis, dot(axis, a0) * (1 - math.cos(t)))
                samples.append(add(centre, rotated))
    return samples, smallest, len(corners)


def conductors(samples, start_axis, end_axis, offsets_start, offsets_mid, offsets_end, taper=14.0):
    """Offsets each conductor from the centerline, starting and ending on its own pin or pad."""
    n = len(samples)
    tangents = [unit(sub(samples[min(i + 1, n - 1)], samples[max(i - 1, 0)])) for i in range(n)]
    normal = sub(start_axis, tuple(c * dot(start_axis, tangents[0]) for c in tangents[0]))
    normal = unit(normal if length(normal) > 1e-6 else (1, 0, 0))
    normals = []
    for t in tangents:
        projected = sub(normal, tuple(c * dot(normal, t) for c in t))
        normal = unit(projected if length(projected) > 1e-6 else normal)
        normals.append(normal)
    # Twist the last stretch so the conductors line up with the end pads.
    t_end = tangents[-1]
    target = sub(end_axis, tuple(c * dot(end_axis, t_end) for c in t_end))
    twist = 0.0
    if length(target) > 1e-6:
        target = unit(target)
        twist = math.atan2(dot(cross(normals[-1], target), t_end), dot(normals[-1], target))
    distance = [0.0]
    for i in range(1, n):
        distance.append(distance[-1] + length(sub(samples[i], samples[i - 1])))
    total = distance[-1] or 1.0
    paths = []
    for c in range(len(offsets_mid)):
        pts = []
        for i in range(n):
            f = max(0.0, (distance[i] / total - 0.55) / 0.45)
            f = f * f * (3 - 2 * f)
            angle = twist * f
            t = tangents[i]
            m = normals[i]
            m = add(add(tuple(x * math.cos(angle) for x in m), cross(t, m), math.sin(angle)), t, dot(t, m) * (1 - math.cos(angle)))
            into = min(1.0, distance[i] / taper)
            left = min(1.0, (total - distance[i]) / taper)
            off = offsets_mid[c]
            off = offsets_start[c] + (off - offsets_start[c]) * into * into * (3 - 2 * into)
            off = offsets_end[c] + (off - offsets_end[c]) * left * left * (3 - 2 * left)
            pts.append(add(samples[i], m, off))
        paths.append(pts)
    return paths


def spread(count, pitch):
    return [(i - (count - 1) / 2) * pitch for i in range(count)]


def build_route(spec):
    """spec: name, colors, od, bend, start=(point, dir, axis), end=(point, dir, axis), via, pitch."""
    p0, d0, a0 = spec["start"]
    p1, d1, a1 = spec["end"]
    lead = spec.get("lead", 3.0)
    points = [p0, add(p0, d0, lead), *spec.get("via", []), add(p1, d1, spec.get("end_lead", lead)), p1]
    samples, smallest, bends = fillet_path(points, spec["bend"])
    count = len(spec["colors"])
    mid = spec.get("offsets", spread(count, spec.get("pitch", spec["od"])))
    start = spec.get("start_offsets", mid)
    end = spec.get("end_offsets", mid)
    paths = conductors(samples, a0, a1, start, mid, end)
    return {
        "name": spec["name"], "r": spec["od"] / 2, "kind": spec.get("kind", "Hookup wire"), "required": spec["bend"],
        "actual": round(smallest, 1) if smallest is not None else None, "bends": bends,
        "check": spec.get("check", True), "check_r": spec.get("check_r"), "ok": smallest is None or smallest >= spec["bend"] - 0.05,
        "length": round(sum(length(sub(samples[i + 1], samples[i])) for i in range(len(samples) - 1))),
        "paths": [{"color": c, "points": [[round(v, 2) for v in q] for q in pts]} for c, pts in zip(spec["colors"], paths)],
        "center": samples,
    }
