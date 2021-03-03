# Needed imports
import sys                      # for exit on error
import math                     # for pi
import json                     # for reading json files
import random                   # for dice values
import functools                # for some utility functions
from datetime import timedelta  # for time periods
import Gempyre                  # for UI
from Gempyre_utils import resource

# The mouse click radius outside drawing radius
FEATHER = 10
# HTML Unicode value for dice graphics
DICE_FACE = '&#127922;'
# HTML Unicode value for a 1st die value
DIE_1 = 9856
# Seconds to show the current die value, when not waiting for user
DICE_WAIT = 1.5

isometric_draw = False


# A peg goes in slot
class Peg:
    def __init__(self, color, slot):
        self.color = color
        self.slot = slot
        self.position = 0

    def draw(self, frame):
        frame.begin_path()
        self.slot.draw_ellipse(frame)
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
        self.isometric = True

    def draw_ellipse(self, frame):
        if isometric_draw:
            frame.save()
            frame.scale(1, 0.5)
            frame.arc(self.x, self.y, self.size, 0, 2 * math.pi)
            frame.restore()
        else:
            frame.arc(self.x, self.y, self.size, 0, 2 * math.pi)

    def draw(self, frame):
        frame.begin_path()
        self.draw_ellipse(frame)
        frame.stroke_style(self.color)
        frame.stroke()

        if self.hilit:
            frame.begin_path()
            self.draw_ellipse(frame)
            frame.fill_style('#1B1B1B2F')
            frame.fill()

        if self.selected:
            frame.begin_path()
            self.draw_ellipse(frame)
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

    def activate(self, color, target):
        selected = []
        for s in self.slots:
            if s.peg and s.peg.color == color and target(s):
                s.selected = True
                selected.append(s)
            else:
                s.selected = False
        return selected

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

    def activate(self, target):
        for s in self.slots:
            if s.peg and target(s):
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


class Goals(Home):
    def __init__(self, d):
        super().__init__(d)

    def is_full(self):
        return len([s for s in self.slots if s.peg]) == len(self.slots)


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
    GAME_OVER = 5

    NEW_RING = 6
    MIN_PLAYERS = 2

    def __init__(self, data, help_function):
        self.width = data['width']
        self.height = data['height']
        self.ring = Ring(data['ring'])
        self.starts = {s['color']: Start(s) for s in data['starts']}
        self.goals = {s['color']: Goals(s) for s in data['goals']}
        self.state = self.START
        self.players = []
        self.player_turn = 0
        self.help = help_function
        self.is_new_ring = False
        self.selected = None

    def draw(self, frame_composer):
        self.ring.draw(frame_composer)
        for s in self.starts.values():
            s.draw(frame_composer)
        for g in self.goals.values():
            g.draw(frame_composer)

    def slot_at(self, x, y):
        return self.ring.slot_at(x, y) or self.current_start().slot_at(x, y) or self.current_goal().slot_at(x, y)

    def clicked(self, x, y):
        assert self.state == self.PICK_MOVER
        self.selected = None
        slot = self.slot_at(x, y)
        print("hit at", slot, slot.peg.color if slot and slot.peg else "Empty")
        if slot and slot.peg and slot.peg.color == self.current_player().color and (
                self.is_new_ring or slot.owner == self.ring):
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
            if self.is_new_ring:
                return True
            return self.turn_inc()
        return False

    def player(self, color):
        for n in self.players:
            if n.color == color:
                return n
        return None

    def current_player(self):
        return self.players[self.player_turn] if self.player_turn < len(self.players) else None

    def set_players(self, player_names):
        self.players = [Player(p, player_names[p]) for p in player_names if player_names[p]]
        if len(self.players) < self.MIN_PLAYERS:
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
            for k in self.goals:
                if self.goals[k].is_full():
                    self.help(self.player(k).name + " won!")
                    self.state = self.GAME_OVER
                    return False
            self.player_turn = 0
        return True

    def dice_thrown(self, value):
        self.is_new_ring = value == self.NEW_RING
        self.players[self.player_turn].current_dice = value
        if self.state == self.SELECT_STARTER:
            self.turn_inc()
            if len([s for s in self.players if s.current_dice < 1]) == 0:
                self.players.sort(key=lambda x: x.current_dice, reverse=True)
                self.state = self.NEXT_TURN
                self.player_turn = 0
                self.help(self.current_player().name.capitalize() + " will start the game!")
            else:
                self.help(self.current_player().name.capitalize() + " throws the dice to see who will be the first.")
            return True
        elif self.state == self.NEXT_TURN:
            assert not self.selected
            self.selected = self.ring.activate(self.current_player().color, self.target_slot)
            if value == self.NEW_RING:
                activated_start = self.current_start().activate(self.target_slot)
                if activated_start:
                    self.selected.append(activated_start)
            if len(self.selected) == 0:
                if self.turn_inc():
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
            if target_pos < slot_count:
                position = (target_pos + self.current_start().entry) % slot_count
                if not self.ring.slots[position].peg or self.ring.slots[position].peg.color != self.current_color():
                    return self.ring.slots[position]
            # It tries to go goal
            else:
                goal_position = target_pos - slot_count
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

    @staticmethod
    def set_draw_mode(mode):
        global isometric_draw
        isometric_draw = True if mode == 'isometric' else False


AUTO_PLAY_ON = 1
AUTO_PLAY_PENDING = 2
AUTO_PLAY_DECIDE = 4


def main():
    # soils console with internal stuff
    # Gempyre.set_debug(Gempyre.DebugLevel.Debug)
    # Just print a greeting to file

    print("Using Gempyre " + str(Gempyre.version()))

    # Construct a Gempyre::Ui
    ui_file = 'gui/timple.html'
    file_map, names = resource.from_file(ui_file, 'gui/favicon.ico', 'gui/hyppy.ogg')
    print(names[ui_file], names[ui_file] == '/timple.html', "names:", names, file_map)
    ui = Gempyre.Ui(file_map, '/timple.html', Gempyre.os_browser())

    # foo = ui.resource('/timple.html')
    # print("html:", ''.join([chr(x) for x in foo]))

    # Then get needed UI components
    canvas = Gempyre.CanvasElement(ui, "canvas")
    dice = Gempyre.Element(ui, "dice")
    start = Gempyre.Element(ui, "start")
    instructions = Gempyre.Element(ui, "instructions")
    restart = Gempyre.Element(ui, "restart")
    draw_mode = Gempyre.Element(ui, "drawing")

    # add audio
    audio = Gempyre.Element(ui, 'audio', ui.root())
    audio.set_attribute('src', 'hyppy.ogg')

    # Read game data file
    with open("gui/data.json", 'r') as f:
        data = json.load(f)

    # Create Game object
    game = Game(data, lambda string: instructions.set_html(string))

    initial_help = "Provide players names before start."
    game.help(initial_help)

    # Compose initial UI graphics
    frame_composer = Gempyre.FrameComposer()
    game.draw(frame_composer)
    canvas.draw_frame(frame_composer)

    # Set Gempyre error handler
    ui.on_error(lambda e: sys.exit(e))

    # Colors what we have
    colors = ['red', 'green', 'blue', 'yellow']
    # List of UI elements holding then the player names
    name_elements = {color: Gempyre.Element(ui, color + "_name") for color in colors}

    # Let's monitor whether names are set
    def on_name_change(_):
        names = {color: name_elements[color].values()['value'] for color in colors}
        if sum([True for nn in names.values() if len(nn) > 0]) >= game.MIN_PLAYERS:
            start.remove_attribute('disabled')
        else:
            start.set_attribute('disabled')
    # Subscribe input changes
    for n in name_elements.values():
        n.subscribe('input', on_name_change)

    # Controls if Dice can be thrown
    next_dice_ok = True

    # The mouse coordinates are in window coordinates, thus we need canvas position
    canvas_rect = None

    # A slot that holds current target slot (when choosing one)
    hilit_slot = None

    is_new_ring = False

    # Auto play state
    auto_play_state = 0

    # ...and have a function to read it
    def on_open():
        nonlocal canvas_rect
        canvas_rect = canvas.rect()
        # Set initial draw mode upon UI
        game.set_draw_mode(draw_mode.values()['value'])

    # ... of which we call upon start, note that we set position absolute in HTML,
    # otherwise these rect may not be valid if page content changes
    ui.on_open(on_open)

    # Function that wipes previous draw and draw a new frame
    def redraw():
        fc = Gempyre.FrameComposer()
        fc.clear_rect(Gempyre.Rect(0, 0, game.width, game.height))
        game.draw(fc)
        canvas.draw_frame(fc)

    def start_auto_play():
        nonlocal auto_play_state
        auto_play_state |= AUTO_PLAY_ON

        def auto_play(tid):
            nonlocal auto_play_state
            if not auto_play_state & AUTO_PLAY_ON:
                ui.stop_timer(tid)
                print("No timer")
                return
            print("nix", next_dice_ok)
            if not next_dice_ok:
                return

            def send_click(at):
                class EventDuck:
                    def __init__(self):
                        self.properties = {}

                event = EventDuck()
                event.properties['clientX'] = str(game.selected[at].x + canvas_rect.x)
                event.properties['clientY'] = str(game.selected[at].y + canvas_rect.y)
                on_click(event)

            print("throw")
            throw_dice(random.randint(0, 5))
            if game.state == game.PICK_MOVER:
                if game.selected and len(game.selected) == 1:
                    print("clicx")
                    send_click(0)
                elif game.selected and auto_play_state & AUTO_PLAY_DECIDE:
                    print("guess")
                    send_click(random.randint(0, len(game.selected) - 1))
                else:
                    print("stop")
                    auto_play_state |= AUTO_PLAY_PENDING
                    ui.stop_timer(tid)
            print("auto play", game.state, auto_play_state)

        ui.start_timer_id(timedelta(seconds=1), False, auto_play)

    # Function called when a Start button is clicked.
    def on_start(_):
        nonlocal auto_play_state
        # the names in those elements
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
        Gempyre.Element(ui, 'start_items').set_attribute('hidden')
        # Show dice (using styles - for some reason attribute wont work)
        dice.set_style('visibility', 'visible')
        # Set auto play mode
        if Gempyre.Element(ui, 'auto_decide').values()['checked'] == 'true':
            auto_play_state |= AUTO_PLAY_DECIDE
        if Gempyre.Element(ui, 'auto_start').values()['checked'] == 'true':
            start_auto_play()

    # Subscribe the start button.
    start.subscribe('click', on_start)

    # Function called when next throw is expected.
    def next_dice():
        print("next dice")
        # Python trick to refer outer scope variable.
        nonlocal next_dice_ok
        # Set icon
        dice.set_html(DICE_FACE)
        # Set color to match with thrower.
        dice.set_style('background-color', game.current_color())
        # Next throw will be ok
        print("niext", game.state)
        if game.state == game.GAME_OVER:
            return
        next_dice_ok = True
        game.help(game.current_player().name.capitalize() + ", throw your dice")
        print("auto statue", auto_play_state)
        if auto_play_state & AUTO_PLAY_PENDING:
            start_auto_play()

    # Function called when dice will be thrown.
    def throw_dice(number):
        nonlocal next_dice_ok
        if not next_dice_ok:
            return

        # Set HTML Unicode icon to reflect the die value
        dice.set_html('&#' + str(DIE_1 + number) + ';')
        # We tell that to game and see if next throw will be ok soon (show a glimpse of current value first)
        if game.dice_thrown(number + 1):
            print("start nix timer")
            ui.start_timer(timedelta(seconds=DICE_WAIT), True, next_dice)
        else:
            assert game.state == game.PICK_MOVER
        next_dice_ok = False
        # We have to redraw UI as game changes may has happen
        redraw()

    # Subscribe a button
    dice.subscribe('click', lambda _: throw_dice(random.randint(0, 5)))

    def key_down(event):
        code = chr(int(float(event.properties['keyCode'])))  # Gempyre returns numbers as float
        if (game.state == game.SELECT_STARTER or game.state == game.NEXT_TURN) and '1' <= code <= '6':
            throw_dice(ord(code) - ord('1'))

    ui.root().subscribe('keydown', key_down, ['keyCode'])

    # Function that shows targets
    def show_targets(e):
        nonlocal hilit_slot
        nonlocal canvas_rect
        # Only if a correct state
        if game.state == game.PICK_MOVER:
            # Get a slot that match with the event coordinates.
            x = float(e.properties['clientX'])
            y = float(e.properties['clientY'])
            x -= canvas_rect.x
            y -= canvas_rect.y
            y = y * 2 if isometric_draw else y
            target = game.slot_at(x, y)
            if target and target.peg and target.peg.color == game.current_player().color and (
                    game.is_new_ring or target.owner == game.ring):
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
        if game.state != game.PICK_MOVER:
            print("not click")
            return
        if hilit_slot:
            hilit_slot.hilit = False
        hilit_slot = None
        # Controls if Dice can be thrown
        x = float(event.properties['clientX']) - canvas_rect.x
        y = float(event.properties['clientY']) - canvas_rect.y
        print("clicking")
        if game.clicked(x, y):
            print("next")
            ui.eval('document.getElementById("' + audio.id() + '").play();')
            next_dice()
        elif game.state == game.GAME_OVER:
            restart.remove_attribute('hidden')
        else:
            assert not auto_play_state & AUTO_PLAY_ON
        print("draw")
        redraw()
        print("clicked")

    # subscribe clicks
    canvas.subscribe('click', on_click, ["clientX", "clientY"])

    def on_reset(_):
        nonlocal auto_play_state
        nonlocal hilit_slot
        nonlocal next_dice_ok
        nonlocal game
        # Reset local state
        auto_play_state = 0
        hilit_slot = None
        next_dice_ok = None
        game = Game(data, game.help)
        game.help(initial_help)
        for k in name_elements:
            name_elements[k].remove_attribute('disabled')
        # Hide start button (using hidden attribute)
        Gempyre.Element(ui, 'start_items').remove_attribute('hidden')
        dice.set_style('visibility', 'hidden')
        restart.set_attribute('hidden')
        redraw()

    def on_set_draw_mode(_):
        game.set_draw_mode(draw_mode.values()['value'])
        redraw()

    restart.subscribe('click', on_reset)

    draw_mode.subscribe('change', on_set_draw_mode)

    # Start the UI, the function wont return until application exits.
    ui.run()


# Python app entry point done nicely
if __name__ == "__main__":
    #Gempyre.set_debug(Gempyre.DebugLevel.Debug_Trace)
    main()
