import cadquery as cq

# Editable params (mm)
length, width, height, wall = 80.0, 45.0, 25.0, 2.0
grip_teeth = 6

outer = cq.Workplane("XY").box(length, width, height)
inner = cq.Workplane("XY").box(length - wall * 2, width - wall * 2, height).translate((0, 0, wall))
body = outer.cut(inner)
# grip ridges on top edges
for i in range(grip_teeth):
    x = -length / 2 + 8 + i * ((length - 16) / max(grip_teeth - 1, 1))
    tooth = cq.Workplane("XY").box(2.0, width + 2.0, 2.0).translate((x, 0, height / 2))
    body = body.union(tooth)

result = body  # orchestrator exports `result`
