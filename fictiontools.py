#!/usr/bin/env python3
# Copyright (c) 2019 Benjamin Holt -- MIT License

"""
Tools for building interactive fiction adventure games using statemachine.py
"""
from collections import defaultdict
import random
import re
# import time

import statemachine as sm
#####


###  Helpers  ###
def adlib(x, joiner=" "):
    "Dynamically assemble messages from nested collections of parts.  Tuples are pieces to be strung together, lists are variants to choose among; anything else is used as a string"
    if type(x) is tuple:
        return joiner.join([ adlib(i) for i in x ])  # Joining with "|" can be helpful to see how messages get put together
    if type(x) is list:
        return adlib(random.choice(x))
    return str(x)


WORD_SPACE_RE = re.compile(r"(\S)\s+(\S)")
PUNCT_SPACE_RE = re.compile(r"([?!.])\s+(\S)")
def message_spacer(m):
    m = WORD_SPACE_RE.sub(r"\1 \2", m)
    m = PUNCT_SPACE_RE.sub(r"\1  \2", m)
    return m
#####


###  Map Maker  ###
class Map:
    def __init__(self, map_str=None):
        self.rooms = defaultdict(dict)  # {name: {"n": name, ...},...}
        if map_str:
            self.parse(map_str)


    def parse(self, map_str):
        map_lines = []
        map_tokens = []
        map_key = {}

        key_section = sm.matchTest(r"\s*Key:")
        key_re = re.compile(r"(?P<key>\w+):\s*(?P<name>\w+)")
        key_match = lambda i,_: key_re.findall(i)
        def add_keys(_,t):
            map_key.update(dict(t.result))

        # Tests and actions:
        map_section = sm.matchTest(r"\s*Map:")
        lex_re = re.compile(r"(?P<room>\[\w+\])|(?P<passage>[-+]+)")  # REM: this pattern doesn't explicitly identify ignored chars, have to check spans
        lex_match = lambda i,_: lex_re.finditer(i)  # REM: finditer result is always truish
        def store_tokens(i,t):
            map_lines.append(i)
            map_tokens.append(list(t.result))

        # Build the parser:
        p = sm.StateMachine("map")
        p.build("map", 
            (key_section, "key"),
            (lex_match, None, store_tokens),
        )
        p.build("key",
            (map_section, "map"),
            (key_match, None, add_keys),
            (sm.trueTest, None),  # Ignore key lines with no definitions
        )
        for l in map_str.splitlines():
            p.input(l)

        self._configure_rooms(map_lines, map_tokens, map_key)


    def _configure_rooms(self, map_lines, map_tokens, map_key):
        def room_name(m):
            r = m.group("room").strip("[]")
            r = map_key.get(r, r)
            return r

        def overlap(*spans):
            start = max(s[0] for s in spans)
            end = min(s[1] for s in spans)
            return end - start if end > start else 0

        def room_search(tokens, span):
            rooms = [ (room_name(t), overlap(span, t.span())) for t in tokens if t.group("room") ]
            if not rooms:
                return None
            (rm, o) = max(rooms, key=lambda x: x[1])
            return rm if o > 0 else None

        vertical_re = re.compile(r"[|+]")
        def vertical_search(i, span):
            for x in range(i-1, -1, -1):
                m = vertical_re.search(map_lines[x], *span)
                if m:
                    # Follow vertical passage chars until we reach a line without one in the right place...
                    span = m.span()
                    continue
                rm = room_search(map_tokens[x], span)
                if rm:
                    # ...then check that line for a room in the right place
                    # print (x,rm)
                    return rm
                else:
                    break  # End of the (vertical) line
            return None

        for i, t_list in enumerate(map_tokens):
            prev_end = None
            prev_room = None
            for token in t_list:
                if prev_end is not None and prev_end != token.start():
                    prev_room = None  # break in the token spans means no connection
                if token.group("room"):
                    room = room_name(token)
                    if prev_room:
                        self.connect(prev_room, room, "e", "w")
                    prev_room = room
                    north_room = vertical_search(i, token.span())
                    if north_room:
                        self.connect(room, north_room, "n", "s")

                # "passage" tokens don't need anything done
                prev_end = token.end()


    def connect(self, rm1, rm2, d1, d2=None, lenient=False):
        if d1 in self.rooms[rm1]:
            if lenient:
                return  # FIXME: never connects d2 here
            raise KeyError(f"{rm1} already has a '{d1}' connection")

        self.rooms[rm1][d1] = rm2
        if d2:
            self.connect(rm2, rm1, d2, lenient=lenient)


    def build(self, world, commands, action, state_mapper=lambda r: r):
        for room in self.rooms.keys():
            directions = self.rooms[room]
            rules = [ (commands[d], state_mapper(r), action) for d,r in directions.items() ]
            world.build(state_mapper(room), *rules)
#####


###  Commands  ###
class Command:
    def __init__(self, test, *syns, action=None, help=None):
        if callable(test):
            self.test = test
            self._syns = syns  # when using a custom callable test, syns are still useful for help
        else:
            self.test = sm.inTest([test, *syns])
            self._syns = [test, *syns]

        self.action = action
        self._help = help


    def __call__(self, i, t):
        return self.test(i, t)


    def help(self):
        if not self._help:
            return None
        if self._syns:
            return f"{', '.join(self._syns)}:\t{self._help}"
        return self._help


    def add_help(sm):
        def helper(*_):
            rules = sm.rules.get(sm.state, []) + sm.rules.get(None, [])
            cmds = ( r for r,*_ in rules if isinstance(r, Command) )
            helps = ( c.help() for c in cmds )
            return "\n".join(h for h in helps if h)
        help_cmd = Command("help", "h", action=helper, help="Print help for available commands (except hidden ones!)")
        sm.add(None, help_cmd, None, help_cmd.action, "Help")
#####


###  REPL  ###
def repl(world)
    time.sleep(0.1)  # HACK: wait for flush; sometimes prompt prints out-of-order with print output in spite of flush=True
    print(world.input(input("Press enter to start. ")), flush=True)
    while True:
        time.sleep(0.1)  # HACK: wait for flush
        out = world.input(input("> "))
        if out:
            print(out, flush=True)
#####


###  Main  ###
if __name__ == "__main__":
    # import sys
    import time
    GRID_MAP = """
    [00]-01--[02][03][04]
     |        |       |
    [05][06]--+--[08][09]
    [10][11][12] [13][14]
     |        |
    [15][16] [17][18][19]
    """
    # TODO: eventually want a command class with "standard" name, synonyms, help, action, etc.  Help action can find command-based rules for the current state and print help
    GO_COMMANDS = {  # Note: action is added by the map builder
        "n": Command("north", "n", help="Go north"),
        "s": Command("south", "s", help="Go south"),
        "e": Command("east", "e", help="Go east"),
        "w": Command("west", "w", help="Go west"),
        "u": Command("up", "u", help="Go up"),
        "d": Command("down", "d", help="Go down"),
    }

    def look_action(i, t):
        s = t.dst if t.dst is not None else t.state
        return s
        # return adlib(messages.get(s, s))
    look_cmd = Command("look", "l", action=look_action, help="Print a description of your surroundings")

    sorry_action = "Sorry, you can't do that."

    world = sm.StateMachine("start")
    # world = StateMachine("start", tracer=20)  # Keep a deeper trace, -1 for unlimited
    # world = StateMachine("start", tracer=Tracer(printer=lambda s: print(f"T: {s}")))  # Complete tracer with prefix

    world.add(state="start", test=sm.trueTest, dst="01", action=look_action, tag="Start")
    m = Map(GRID_MAP)
    m.connect("01", "00", "w")
    m.connect("01", "02", "e")
    m.build(world, GO_COMMANDS, look_action)

    world.add(None, look_cmd, None, look_cmd.action, tag="Look")
    world.add(None, "xyzzy", "01", look_action, tag="Magic")
    Command.add_help(world)
    world.add(None, lambda i,_: i != "crash", None, sorry_action, tag="Not crash")  # You can type "crash" to dump the state machine's trace

    print("Grid World", flush=True)
    time.sleep(0.1)  # HACK: wait for flush; sometimes prompt prints out-of-order with print output in spite of flush=True
    print(world.input(input("Press enter to start. ")), flush=True)
    while True:
        time.sleep(0.1)  # HACK: wait for flush
        out = world.input(input("> "))
        if out:
            print(out, flush=True)
#####
