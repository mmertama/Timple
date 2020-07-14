import os
import sys
import math
import json
import random
import Telex

FEATHER = 10


class Peg:
    def __init__(self, color, slot):
        self.color = color
        self.slot = slot

    def draw(self, frame):
        frame.begin_path()
        frame.arc(self.slot.x - self.slot.size / 2, self.slot.y - self.slot.size / 2, self.slot.size, 0, 2 * math.pi)
        frame.fill_style(self.color)
        frame.fill()


class Slot:
    def __init__(self, d):
        self.x = d['x']
        self.y = d['y']
        self.size = float(d['size'])
        self.selected = False
        self.peg = Peg(d['color'], self) if d['color'] else None

    def draw(self, frame):
        frame.begin_path()
        frame.arc(self.x - self.size / 2, self.y - self.size / 2, self.size, 0, 2 * math.pi)
        frame.stroke()

        if self.selected:
            frame.begin_path()
            frame.arc(self.x - self.size / 2, self.y - self.size / 2, self.size * 2, 0, 2 * math.pi)
            frame.stroke_style("#2F2F2F")
            frame.stroke()

        if self.peg:
            self.peg.draw(frame)

    def clicked(self, x, y):
        return self.is_in(x, y)

    def is_in(self, x, y):
        return math.fabs(self.x - x) <= (self.size + FEATHER) \
               and math.fabs(self.y - y) <= (self.size + FEATHER)

    def select(self, select):
        self.selected = select


class Ring:
    def __init__(self, d):
        self.x = d['x']
        self.y = d['y']
        self.slots = [Slot(s) for s in d['slots']]

    def draw(self, frame):
        for s in self.slots:
            s.draw(frame)

    def clicked(self, x, y):
        for s in self.slots:
            if s.clicked(x, y):
                return s
        return None


class Home:
    def __init__(self, d):
        self.slots = [Slot(s) for s in d['slots']]

    def draw(self, frame):
        for s in self.slots:
            s.draw(frame)

    def clicked(self, x, y):
        for s in self.slots:
            if s.clicked(x, y):
                return s
        return None


class Game:
    def __init__(self, data):
        self.width = data['width']
        self.height = data['height']
        self.ring = Ring(data['ring'])
        self.starts = [Home(s) for s in data['starts']]
        self.goals = [Home(s) for s in data['goals']]
        self.selected = None
        self.state = "START"

    def draw(self, frame_composer):
        self.ring.draw(frame_composer)
        for s in self.starts:
            s.draw(frame_composer)
        for g in self.goals:
            g.draw(frame_composer)

    def clicked(self, x, y):
 #       if self.state == "START":
 #           return
        if self.swap(self.ring.clicked(x, y)):
            return True
        for s in self.starts:
            if self.swap(s.clicked(x, y)):
                return True
        for g in self.goals:
            if self.swap(g.clicked(x, y)):
                return True
        return False

    def swap(self, selected):
        if not selected:
            return False
        if self.selected:
            self.selected.select(False)
        self.selected = selected
        selected.select(True)
        return True

    def dice_thrown(self, value):
        print(value)


def main():
    # Telex.set_debug()
    print(Telex.version())
    ui_file = os.path.dirname(os.path.realpath(__file__)) + '/gui/timple.html'

    ui = Telex.Ui(ui_file)

    canvas = Telex.CanvasElement(ui, "canvas")
    dice = Telex.Element(ui, "dice")
    start = Telex.Element(ui, "start")

    with open("gui/data.json", 'r') as f:
        data = json.load(f)

    game = Game(data)

    frame_composer = Telex.FrameComposer()

    game.draw(frame_composer)

    canvas.draw_frame(frame_composer)

    ui.on_error(lambda e: sys.exit(e))

    def on_click(event):
        fc = Telex.FrameComposer()
        fc.clear_rect(Telex.Rect(0, 0, game.width, game.height))
        game.clicked(float(event.properties['clientX']), float(event.properties['clientY']))
        game.draw(fc)
        canvas.draw_frame(fc)

    canvas.subscribe('click', on_click, ["clientX", "clientY"])

    def on_start(_):
        colors = ['red', 'green', 'blue', 'yellow']
        name_elements = {color: Telex.Element(ui, color + "_name") for color in colors}
        names = {color: name_elements[color].values()['value'] for color in colors}
        print(names)
        for k in name_elements:
            name_elements[k].set_attribute('disabled')
        start.set_attribute('hidden')
        dice.remove_attribute('hidden')

    start.subscribe('click', on_start)

    def throw_dice(_):
        number = random.randint(0, 5)
        dice.set_html('&#' + str(9856 + number) + ';')
        game.dice_thrown(number + 1)

    dice.subscribe('click', throw_dice)

    ui.run()


if __name__ == "__main__":
    main()
