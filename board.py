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
DICE_WAIT = 1.5


# A peg goes in slot
class Peg:
    def __init__(self, color, slot):
        self.color = color
        self.slot = slot
        self.position = 0

    def draw(self, frame):
        frame.begin_path()
        frame.arc(self.slot.x, self.slot.y, self.slot.size, 0, 2 * math.pi)
        frame.fill_style(self.color)
        frame.fill()

    def reset(self, slot):
        self.slot.peg = None
        slot.peg = self
        self.slot = slot
        self.position = 0


# Game is set of slots
class Slot:
    def __init__(self, d, owner, color="black"):
        self.x = float(d['x'])
        self.y = float(d['y'])
        self.size = float(d['size'])
        self.selected = False
        self.peg = Peg(d['color'], self) if d['color'] else None
        self.color = color
        self.owner = owner
        self.hilit = False

    def draw(self, frame):
        frame.begin_path()
        frame.arc(self.x, self.y, self.size, 0, 2 * math.pi)
        frame.stroke_style(self.color)
        frame.stroke()

        if self.hilit:
            frame.begin_path()
            frame.arc(self.x, self.y, self.size * 2, 0, 2 * math.pi)
            frame.fill_style('#1B1B1B2F')
            frame.fill()

        if self.selected:
            frame.begin_path()
            frame.arc(self.x, self.y, self.size * 2, 0, 2 * math.pi)
            frame.stroke_style('#2F2F2F')
            frame.stroke()

        if self.peg:
            self.peg.draw(frame)

    def is_in(self, x, y):
        return math.fabs(self.x - x) <= (self.size + FEATHER) \
               and math.fabs(self.y - y) <= (self.size + FEATHER)

    def move(self, other, steps):
        assert self.peg
        assert not other.peg
        self.peg.position += steps
        self.peg.slot = other
        other.peg = self.peg
        self.peg = None


class Ring:
    def __init__(self, d):
        self.x = d['x']
        self.y = d['y']
        self.slots = [Slot(s, self) for s in d['slots']]

    def draw(self, frame):
        for s in self.slots:
            s.draw(frame)

    def slot_at(self, x, y):
        for s in self.slots:
            if s.is_in(x, y):
                return s
        return None

    def set_active(self, color):
        selected_count = 0
        for s in self.slots:
            if s.peg and s.peg.color == color:
                s.selected = True
                selected_count += 1
            else:
                s.selected = False
        return selected_count

    def deactivate(self):
        for s in self.slots:
            s.selected = False


class Home:
    def __init__(self, d):
        self.color = d['color']
        self.entry = int(d['entry'])
        self.slots = [Slot(s, self, self.color) for s in d['slots']]

    def draw(self, frame):
        for s in self.slots:
            s.draw(frame)

    def slot_at(self, x, y):
        for s in self.slots:
            if s.is_in(x, y):
                return s
        return None

    def count(self):
        return len([s for s in self.slots if s.peg])


class Start(Home):
    def __init__(self, d):
        super().__init__(d)

    def activate(self):
        for s in self.slots:
            if s.peg:
                s.selected = True
                return s
        return None

    def deactivate(self):
        for s in self.slots:
            s.selected = False

    def is_active(self):
        return functools.reduce(lambda a, b: a or b, self.slots)

    def return_home(self, peg):
        for s in self.slots:
            if not s.peg:
                peg.reset(s)
                return


class Player:
    def __init__(self, color, name):
        self.color = color
        self.name = name.rstrip()
        self.current_dice = -1


class Game:
    START = 1
    PICK_MOVER = 2
    SELECT_STARTER = 3
    NEXT_TURN = 4

    def __init__(self, data, help_function):
        self.width = data['width']
        self.height = data['height']
        self.ring = Ring(data['ring'])
        self.starts = {s['color']: Start(s) for s in data['starts']}
        self.goals = {s['color']: Home(s) for s in data['goals']}
        self.selected = None
        self.state = self.START
        self.players = []
        self.player_turn = 0
        self.help = help_function
        self.no_choice = True

    def draw(self, frame_composer):
        self.ring.draw(frame_composer)
        for s in self.starts.values():
            s.draw(frame_composer)
        for g in self.goals.values():
            g.draw(frame_composer)

    def slot_at(self, x, y):
        return self.ring.slot_at(x, y) or self.current_start().slot_at(x, y) or self.current_goal().slot_at(x, y)

    def clicked(self, x, y):
        slot = self.slot_at(x, y)
        if slot and slot.peg and slot.peg.color == self.current_player().color:
            target = self.target_slot(slot)
            if not target:
                return False
            if target.peg:
                self.starts[target.peg.color].return_home(target.peg)
            self.ring.deactivate()
            self.current_start().deactivate()
            if slot.owner == self.current_start():
                slot.move(target, 0)
            else:
                slot.move(target, self.current_player().current_dice)
            self.state = self.NEXT_TURN
            self.turn_inc()
            return True
        return False

    def current_player(self):
        return self.players[self.player_turn] if self.player_turn < len(self.players) else None

    def set_players(self, player_names):
        self.players = [Player(p, player_names[p]) for p in player_names if player_names[p]]
        if len(self.players) < 2:
            return
        self.state = self.SELECT_STARTER
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
        if self.state == self.SELECT_STARTER:
            self.turn_inc()
            if len([s for s in self.players if s.current_dice < 1]) == 0:
                self.players.sort(key=lambda x: x.current_dice, reverse=True)
                self.state = self.NEXT_TURN
                self.player_turn = 0
                self.help(self.current_player().name.capitalize() + " will start the game!")
                # this is different than in Kimble
                for start in self.starts.values():
                    s = start.slots[0]
                    t = self.ring.slots[start.entry]
                    s.move(t, 0)
            else:
                self.help(self.current_player().name.capitalize() + " throws the dice to see who will be the first.")
            return True
        elif self.state == self.NEXT_TURN:
            selected_count = self.ring.set_active(self.current_player().color)
            if value == 6:
                activated_start = self.current_start().activate()
                if self.target_slot(activated_start):
                    selected_count += 1
                else:
                    activated_start.selected = False
            self.no_choice = selected_count <= 1
            has_target = next((s for s in self.ring.slots if s.selected and self.target_slot(s)), None)
            if selected_count == 0 or not has_target:
                self.turn_inc()
                self.help("Cannot move, pass turn to " + self.current_player().name.capitalize())
                return True
            self.help(self.current_player().name.capitalize() + " do your move.")
            self.state = self.PICK_MOVER
        elif self.state == self.PICK_MOVER:
            None
        return False

    def target_slot(self, slot):
        assert slot.peg  # Slot must have a color!
        assert slot.peg.color == self.current_color()  # Assumed that same as the current color!
        assert 1 <= self.current_player().current_dice <= 6  # Shall have a valid die value!

        # If slot in ring
        if slot.owner == self.ring:
            slot_count = len(self.ring.slots)
            target_pos = slot.peg.position + self.current_player().current_dice
            if target_pos <= slot_count:
                position = (target_pos + self.current_start().entry) % slot_count
                if not self.ring.slots[position].peg or self.ring.slots[position].peg.color != self.current_color():
                    return self.ring.slots[position]
            # It tries to go goal
            else:
                goal_position = (target_pos - slot_count) - 1
                # if we can fit it in
                if goal_position < len(self.current_goal().slots) and not self.current_goal().slots[goal_position].peg:
                    return self.current_goal().slots[goal_position]
                # is it one of starts, and can we go (or event eat)?
        elif slot.owner == self.current_start() and self.current_start().is_active():
            start_pos = self.current_start().entry
            if not self.ring.slots[start_pos].peg or self.ring.slots[start_pos].peg.color != self.current_color():
                return self.ring.slots[start_pos]
        return None

    def get_activated(self):
        return [s for s in self.ring.slots if s.selected] + [s for s in self.current_start().slots if s.selected]


def main():
    # This soils console with internal stuff
    # Telex.set_debug()
    # Just print a greeting to file
    print("Using Telex " + str(Telex.version()))

    # Construct a Telex::Ui
    ui_file = 'gui/timple.html'
    ui = Telex.Ui(ui_file)

    # Then get needed UI components
    canvas = Telex.CanvasElement(ui, "canvas")
    dice = Telex.Element(ui, "dice")
    start = Telex.Element(ui, "start")
    instructions = Telex.Element(ui, "instructions")

    # Read game data file
    with open("gui/data.json", 'r') as f:
        data = json.load(f)

    # Create Game object
    game = Game(data, lambda string: instructions.set_html(string))

    # Compose initial UI graphics
    frame_composer = Telex.FrameComposer()
    game.draw(frame_composer)
    canvas.draw_frame(frame_composer)

    # Set Telex error handler
    ui.on_error(lambda e: sys.exit(e))

    # The mouse coordinates are in window coordinates, thus we need canvas position
    canvas_rect = None

    # ...and have a function to read it
    def on_open():
        nonlocal canvas_rect
        canvas_rect = canvas.rect()
    # ... of which we call upon start
    ui.on_open(on_open)

    # Function that wipes previous draw and draw a new frame
    def redraw():
        fc = Telex.FrameComposer()
        fc.clear_rect(Telex.Rect(0, 0, game.width, game.height))
        game.draw(fc)
        canvas.draw_frame(fc)

    # Function called when a Start button is clicked.
    def on_start(_):
        # Colors what we have
        colors = ['red', 'green', 'blue', 'yellow']
        # List of UI elements holding then the player names
        name_elements = {color: Telex.Element(ui, color + "_name") for color in colors}
        # ...and the names in those
        names = {color: name_elements[color].values()['value'] for color in colors}
        # Apply those to UI
        game.set_players(names)
        # If game state still start
        if game.state == game.START:
            game.help("Set player names")
            return
        # Set dice color same as the current player color
        dice.set_style('background-color', game.current_color())
        # Disable further name changes
        for k in name_elements:
            name_elements[k].set_attribute('disabled')
        # Hide start button (using hidden attribute)
        start.set_attribute('hidden')
        # Show dice (using styles - for some reason attribute wont work)
        dice.set_style('visibility', 'visible')

    # Subscribe The start button.
    start.subscribe('click', on_start)

    # Controls if Dice can be thrown
    next_dice_ok = True

    # Function called when next throw is expected.
    def next_dice():
        # Python trick to refer outer scope variable.
        nonlocal next_dice_ok
        # Set icon
        dice.set_html(DICE_FACE)
        # Set color to match with thrower.
        dice.set_style('background-color', game.current_color())
        # Next throw will be ok
        next_dice_ok = True
        game.help(game.current_player().name.capitalize() + ", throw your dice")

    # Function called when dice will be thrown.
    def throw_dice(_):
        nonlocal next_dice_ok
        if not next_dice_ok:
            return
        # Get a random die number
        number = random.randint(0, 5)
        # Set HTML Unicode icon to reflect the die value
        dice.set_html('&#' + str(DIE_1 + number) + ';')
        # We tell that to game and see if next throw will be ok soon (show a glimpse of current value first)
        if game.dice_thrown(number + 1):
            ui.start_timer(timedelta(seconds=DICE_WAIT), True, next_dice)
        next_dice_ok = False
        # We have to redraw UI as game changes may has happen
        redraw()

    # Subscribe a button
    dice.subscribe('click', throw_dice)

    # A slot that holds current target slot (when choosing one)
    hilit_slot = None

    # Function that shows targets
    def show_targets(e):
        nonlocal hilit_slot
        nonlocal canvas_rect
        # Only if a correct state
        if game.state == game.PICK_MOVER:
            # Get a slot that match with the event coordinates.
            x = float(e.properties['clientX']) - canvas_rect.x
            y = float(e.properties['clientY']) - canvas_rect.y
            target = game.slot_at(x, y)
            if target and target.peg and target.peg.color == game.current_player().color:
                slot = game.target_slot(target)
                # Erase old hi-light graphics, if set
                if hilit_slot:
                    hilit_slot.hilit = False
                # Set a new hi-light, if found
                hilit_slot = slot
                # Apply a new hi-light graphics, if found
                if hilit_slot:
                    hilit_slot.hilit = True
            elif hilit_slot:
                hilit_slot.hilit = False
                hilit_slot = None
            redraw()

    # Subscribe mouse moves, they get often - thus we filter ones coming < 100ms from previous
    canvas.subscribe('mousemove', show_targets,
                     ["clientX", "clientY"], timedelta(milliseconds=100))

    # mouse click handler
    def on_click(event):
        nonlocal next_dice_ok
        nonlocal hilit_slot
        nonlocal canvas_rect
        if hilit_slot:
            hilit_slot.hilit = False
        hilit_slot = None
        # Controls if Dice can be thrown
        x = float(event.properties['clientX']) - canvas_rect.x
        y = float(event.properties['clientY']) - canvas_rect.y
        if game.clicked(x, y):
            next_dice()
        redraw()

    # subscribe clicks
    canvas.subscribe('click', on_click, ["clientX", "clientY"])

    # Start the UI, the function wont return until application exits.
    ui.run()


# Python app entry point done nicely
if __name__ == "__main__":
    main()
