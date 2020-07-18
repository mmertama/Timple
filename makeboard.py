import math
import json


class Slot:
    def __init__(self, x, y, size, color=None):
        self.x = x
        self.y = y
        self.size = size
        self.color = color

    def data(self):
        return {'x': int(self.x),
                'y': int(self.y),
                'size': int(self.size),
                'color': self.color}


class Ring:
    def __init__(self, x, y, rad, size, count):
        self.x = x
        self.y = y
        self.slots = []
        step = (2 * math.pi) / count
        r = 0
        for i in range(0, count):
            xx = math.sin(r) * rad
            yy = math.cos(r) * rad
            self.slots.append(Slot(xx + x, yy + y, size))
            r += step

    def data(self):
        return {'x': self.x,
                'y': self.y,
                'slots': [s.data() for s in self.slots]
                }


class Home:
    def __init__(self, color, entry):
        self.slots = []
        self.color = color
        self.entry = entry

    def data(self):
        return {'color': self.color,
                'entry': int(self.entry),
                'slots': [s.data() for s in self.slots]}


class Start(Home):
    def __init__(self, x, y, angle, distance, width, size, count, direction, color, entry):
        super().__init__(color, entry)
        px = math.sin(angle) * distance
        py = math.cos(angle) * distance

        dx = math.sin(angle + direction) * width / count
        dy = math.cos(angle + direction) * width / count

        x0 = (x + px) - (dx * ((count - 1) / 2))
        y0 = (y + py) - (dy * ((count - 1) / 2))

        for i in range(0, count):
            self.slots.append(Slot(x0, y0, size, color))
            x0 += dx
            y0 += dy


class Goal(Home):
    def __init__(self, x, y, angle, distance, width, size, count, direction, color, entry):
        super().__init__(color, entry)
        px = math.sin(angle) * (distance + width)
        py = math.cos(angle) * (distance + width)

        dx = math.sin(angle + direction) * width / count
        dy = math.cos(angle + direction) * width / count

        x0 = (x + px)
        y0 = (y + py)

        for i in range(0, count):
            self.slots.append(Slot(x0, y0, size))
            x0 -= dx
            y0 -= dy


def main():
    encoder = json.JSONEncoder(indent=1)
    ball_rad = 6
    ring_count = 20
    ring = Ring(250, 250, 150, ball_rad, ring_count)
    starts = []

    colors = ["red", "green", "blue", "yellow"]
    entry = 0

    for a in range(0, 4):
        starts.append(Start(250, 250,
                            a * (math.pi / 2)
                            , 200, 100, ball_rad, 4, math.pi / 2, colors[a], entry))
        entry += ring_count / 4

    goals = []
    entry = ring_count
    for a in range(0, 4):
        goals.append(Goal(250, 250,
                          a * (math.pi / 2), 20, 100, ball_rad, 4, 0, colors[a], entry))
        entry += ring_count / 4

    data = encoder.encode({'width': 500,
                           'height': 500,
                           'ring': ring.data(),
                           'starts': [s.data() for s in starts],
                           'goals': [g.data() for g in goals]})

    with open("gui/data.json", 'w') as f:
        f.write(data)


if __name__ == "__main__":
    main()
