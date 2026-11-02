"""
    Filename: assembly_check.py
    Description:
        Simulates the build order. Each part slides in along its real path, and the check
        reports the first thing it hits. Also lists cables that cross between the front
        shell and the back cover, because those must be connected before the cover closes.
"""

import block_p as b
from build123d import Pos


def hits(part, installed, step_axis, travel):
    found = {}
    for d in range(5, travel + 1, 5):
        moved = Pos(*[v * d for v in step_axis]) * part
        box_a = moved.bounding_box()
        for name, shape in installed.items():
            box_b = shape.bounding_box()
            if box_a.max.X < box_b.min.X or box_a.min.X > box_b.max.X or box_a.max.Y < box_b.min.Y or box_a.min.Y > box_b.max.Y or box_a.max.Z < box_b.min.Z or box_a.min.Z > box_b.max.Z:
                continue
            volume = b.overlap(moved, shape)
            if volume > 1:
                found.setdefault(name, (d, volume))
    return found


def main():
    shell = b.front_shell()
    ring = b.diffuser()
    upper, lower = b.back_covers()
    brackets = b.pi_brackets()
    parts = b.stand_in_parts()
    installed = {"shell": shell}
    BACK = (0, 0, -1)
    steps = [
        ("Stem splice, from the back", b.stem_splice(), BACK, 60),
        ("Left speaker, from the back", parts["Speaker left"], BACK, 60),
        ("Right speaker, from the back", parts["Speaker right"], BACK, 60),
        ("Screen, from the back", b.union([parts["Screen"], parts["Screen board"], parts["Screen ports"]]), BACK, 70),
        ("Screen clips, from the back", b.union([b.screen_clip(x, y) for x in b.CLAMP_XS for y in (b.CLAMP_TOP_Y, b.CLAMP_BOTTOM_Y)]), BACK, 60),
        ("Power jack, from below", parts["Power jack"], (0, -1, 0), 30),
    ]
    print("Part paths")
    for name, part, axis, travel in steps:
        result = hits(part, installed, axis, travel)
        print(f"  {name}: {'clear' if not result else result}")
        installed[name] = part
    print(f"  Diffuser, from the front: {'clear' if not hits(ring, {'shell': shell}, (0, 0, 1), 30) else 'blocked'}")

    tray = b.union([upper, *brackets, parts["Pi case bottom"], parts["Pi case top"], parts["Pi connectors"], parts["Cable plugs"],
                    parts["Converter"], parts["USB audio dongle"], parts["Level shifter board"], parts["Level shifter parts"]])
    print(f"  Upper cover with electronics, closing: {hits(tray, installed, BACK, 60) or 'clear'}")

    print("\nCables crossing between the shell and the cover")
    for r in b.wire_routes():
        print(f"  {r['name']:30s} {r['length']:4d} mm")


if __name__ == "__main__":
    main()
