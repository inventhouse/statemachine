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
def adlib(x):
    "Dynamically assemble messages from nested collections of parts.  Tuples are pieces to be strung together, lists are variants to choose among; anything else is used as a string"
    if type(x) is tuple:
        return "".join([ adlib(i) for i in x ])  # Joining with "|" can be helpful to see how messages get put together
    if type(x) is list:
        return adlib(random.choice(x))
    return str(x)
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
                        self.rooms[room]["w"] = prev_room
                        self.rooms[prev_room]["e"] = room
                    prev_room = room
                    north_room = vertical_search(i, token.span())
                    if north_room:
                        self.rooms[room]["n"] = north_room
                        self.rooms[north_room]["s"] = room

                # "passage" tokens don't need anything done
                prev_end = token.end()


    def build(self, sm, commands, action, state_mapper=lambda r: r):
        for room in self.rooms.keys():
            directions = self.rooms[room]
            rules = [ (commands[d], state_mapper(r), action) for d,r in directions.items() ]
            sm.build(state_mapper(room), *rules)
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
    GO_COMMANDS = {
        "n": sm.inTest(["n", "north"]),
        "s": sm.inTest(["s", "south"]),
        "e": sm.inTest(["e", "east"]),
        "w": sm.inTest(["w", "west"]),
    }

    def lookAction(i, t):
        s = t.dst if t.dst is not None else t.state
        return s
        # return adlib(messages.get(s, s))

    sorryAction = "Sorry, you can't do that."

    world = sm.StateMachine("start")
    # world = StateMachine("start", tracer=20)  # Keep a deeper trace, -1 for unlimited
    # world = StateMachine("start", tracer=Tracer(printer=lambda s: print(f"T: {s}")))  # Complete tracer with prefix

    world.add(state="start", test=sm.trueTest, dst="01", action=lookAction, tag="Start")
    world.build("01",
        (GO_COMMANDS["e"], "02", lookAction),
        (GO_COMMANDS["w"], "00", lookAction),
    )
    m = Map(GRID_MAP)
    m.build(world, GO_COMMANDS, lookAction)

    world.add(None, sm.inTest(["l", "look",]), None, lookAction, tag="Look")
    world.add(None, "xyzzy", "01", lookAction, tag="Look")
    world.add(None, lambda i,_: i != "crash", None, sorryAction, tag="Not crash")  # You can type "crash" to dump the state machine's trace

    print("Grid World", flush=True)
    time.sleep(0.1)  # HACK: wait for flush; sometimes prompt prints out-of-order with print output in spite of flush=True
    print(world.input(input("Press enter to start. ")), flush=True)
    while True:
        time.sleep(0.1)  # HACK: wait for flush
        out = world.input(input("> "))
        if out:
            print(out, flush=True)
#####
