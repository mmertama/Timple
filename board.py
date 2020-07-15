import os
import sys
import math
import json
import random
import functools
from datetime import timedelta
import Telex

FEATHER = 10
DICE_FACE = '&#127922;'
DIE_1 = 9856
DICE_WAIT = 3


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
    def __init__(self, d, color="black"):
        self.x = d['x']
        self.y = d['y']
        self.size = float(d['size'])
        self.selected = False
        self.peg = Peg(d['color'], self) if d['color'] else None
        self.color = color

    def draw(self, frame):
        frame.begin_path()
        frame.arc(self.x - self.size / 2, self.y - self.size / 2, self.size, 0, 2 * math.pi)
        frame.stroke_style(self.color)
        frame.stroke()

        if self.selected:
            frame.begin_path()
            frame.arc(self.x - self.size / 2, self.y - self.size / 2, self.size * 2, 0, 2 * math.pi)
            frame.stroke_style('#2F2F2F')
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

    def set_active(self, color):
        changed_any = False
        for s in self.slots:
            if s.peg and s.peg.color == color:
                s.selected = True
                changed_any = True
            else:
                s.selected = False
        return changed_any


class Home:
    def __init__(self, d):
        self.color = d['color']
        self.slots = [Slot(s, self.color) for s in d['slots']]

    def draw(self, frame):
        for s in self.slots:
            s.draw(frame)

    def clicked(self, x, y):
        for s in self.slots:
            if s.clicked(x, y):
                return s
        return None

    def count(self):
        return len([s for s in self.slots if s.peg])


class Start(Home):
    def __init__(self, d):
        super().__init__(d)

    def set_active(self):
        for s in self.slots:
            if s.peg:
                s.selected = True
                return


class Player:
    def __init__(self, color, name):
        self.color = color
        self.name = name.rstrip()
        self.current_dice = -1


class Game:
    def __init__(self, data, help_function):
        self.width = data['width']
        self.height = data['height']
        self.ring = Ring(data['ring'])
        self.starts = {s['color']: Start(s) for s in data['starts']}
        self.goals = {s['color']: Home(s) for s in data['goals']}
        self.selected = None
        self.state = "START"
        self.players = []
        self.player_turn = 0
        self.help = help_function

    def draw(self, frame_composer):
        self.ring.draw(frame_composer)
        for s in self.starts.values():
            s.draw(frame_composer)
        for g in self.goals.values():
            g.draw(frame_composer)

    def clicked(self, x, y):
        if self.state != "PLAY":
            return
        if self.swap(self.ring.clicked(x, y)):
            return True
        for s in self.starts.values():
            if self.swap(s.clicked(x, y)):
                return True
        for g in self.goals.values():
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

    def current_player(self):
        return self.players[self.player_turn] if self.player_turn < len(self.players) else None

    def set_players(self, player_names):
        self.players = [Player(p, player_names[p]) for p in player_names if player_names[p]]
        if len(self.players) < 2:
            return
        self.state = "INIT"
        self.player_turn = 0
        self.help(self.current_player().name.capitalize() + " throws the dice to see who will be the first.")

    def current_color(self):
        return self.current_player().color if self.current_player() else 'white'

    def current_start(self):
        return self.starts[self.current_player().color]

    def current_goal(self):
        return self.goals[self.current_player().color]

    def turn_inc(self):
        self.player_turn += 1
        if self.player_turn >= len(self.players):
            self.player_turn = 0

    def dice_thrown(self, value):
        self.players[self.player_turn].current_dice = value
        if self.state == "INIT":
            self.turn_inc()
            if len([s for s in self.players if s.current_dice < 1]) == 0:
                self.players.sort(key=lambda x: x.current_dice, reverse=True)
                self.state = "PLAY"
                self.player_turn = 0
                self.help(self.current_player().name.capitalize() + " will start the game!")
            else:
                self.help(self.current_player().name.capitalize() + " throws the dice to see who will be the first.")
            return True
        if self.state == "PLAY":
            if value == 6:
                self.current_start().set_active()
            found_any = self.ring.set_active(self.current_player().color)
            if not (value == 6 and self.current_start().count() > 0) and not found_any:
                self.turn_inc()
                self.help("Nobody can move... " + self.current_player().name.capitalize() + " throws next.")
                return True
            self.help(self.current_player().name.capitalize() + " do your move.")
        return False


def main():
    # Telex.set_debug()
    print("Using Telex " + str(Telex.version()))
    ui_file = os.path.dirname(os.path.realpath(__file__)) + '/gui/timple.html'

    ui = Telex.Ui(ui_file)

    canvas = Telex.CanvasElement(ui, "canvas")
    dice = Telex.Element(ui, "dice")
    start = Telex.Element(ui, "start")
    instructions = Telex.Element(ui, "instructions")

    with open("gui/data.json", 'r') as f:
        data = json.load(f)

    game = Game(data, lambda string: instructions.set_html(string))

    frame_composer = Telex.FrameComposer()

    game.draw(frame_composer)

    canvas.draw_frame(frame_composer)

    ui.on_error(lambda e: sys.exit(e))

    def redraw():
        fc = Telex.FrameComposer()
        fc.clear_rect(Telex.Rect(0, 0, game.width, game.height))
        game.draw(fc)
        canvas.draw_frame(fc)

    def on_click(event):
        game.clicked(float(event.properties['clientX']), float(event.properties['clientY']))
        redraw()

    canvas.subscribe('click', on_click, ["clientX", "clientY"])

    def on_start(_):
        colors = ['red', 'green', 'blue', 'yellow']
        name_elements = {color: Telex.Element(ui, color + "_name") for color in colors}
        names = {color: name_elements[color].values()['value'] for color in colors}
        game.set_players(names)
        if game.state == "START":
            game.help("Set player names")
            return
        dice.set_style('background-color', game.current_color())
        for k in name_elements:
            name_elements[k].set_attribute('disabled')
        start.set_attribute('hidden')
        dice.set_style('visibility', 'visible')

    start.subscribe('click', on_start)

    next_dice_ok = True

    def next_dice():
        nonlocal next_dice_ok
        dice.set_html(DICE_FACE)
        dice.set_style('background-color', game.current_color())
        next_dice_ok = True
        redraw()

    def throw_dice(_):
        nonlocal next_dice_ok
        if not next_dice_ok:
            return
        number = random.randint(0, 5)
        dice.set_html('&#' + str(DIE_1 + number) + ';')
        if game.dice_thrown(number + 1):
            ui.start_timer(timedelta(seconds=DICE_WAIT), True, next_dice)
        next_dice_ok = False
        redraw()

    dice.subscribe('click', throw_dice)

    ui.run()


if __name__ == "__main__":
    main()
