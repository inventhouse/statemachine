Interactive Fiction Games
=========================
Notes about using [`statemachine.py`](statemachine.py) to build interactive fiction games


SmoothSailing
-------------
Simple game that directly builds a tiny world of states and actions


CabinInTheWoods
---------------
More advanced game that uses [`fictiontools.py`](fictiontools.py) to build a more playable world


Fiction Tools
-------------
A library of tools to help with writing interactive fiction adventure games

### To Do:

- DONE: maybe "map linter"?
    - DONE: `raise` if any rooms try to set redundant connections

- DONE: `connect` method to make it easier to make one-off connections easily
- DONE: `up` and `down` directions for use with `connect`
    - intercardinal directions, too?
    - hoist `go_commands` into ft?
    - more specialized `go` command?
    - `exits` command?

- DONE: general-purpose `help` command
    - DONE: `command` class to support `help` command

- `room` class?

- inventory system
    - mix-in?
    - player inventory
    - room inventory

- general-purpose repl
    - mechanism for quitting
    - automatically add `help` and `quit`

- Docs, sooo many docs...

#### Doneyard:

- DONE: Devise map "language"
    - DONE: "rooms" are labeled with `\[\w+\]`
        - DONE: immediately adjacent rooms connect by default
        - DONE: "Key" to define short names for rooms per-mapstring
    - DONE: symbols for horizontal and vertical passages
        - DONE: allow vertical or horizontal passages to cross each other, but they only connect at "rooms"
        - DONE: may need to distinguish between horizontal (`[-+]`) and vertical (`[|+]`) passages
    - DONE: comments - simply ignore non-room / non-passage chars
    - DONE: symbols for "warp to"? - allowing repeated room names could enable "warp"
    - DONE: multiple map sections? - parsing multiple map strings with names in common could enable "stitching"
    - PUNT: up/down passages? - use comments and manual rules for advanced things to start
    - PUNT: map namespaces?
- DONE: map parsing
    - DONE: split lines
    - PUNT: strip #-comments
    - PUNT: simplify logic by regularizing the board?
        - square up lines
        - wrap each line in null-passages on both ends
        - add top and bottom null-passage lines
    - DONE: find each room on a line and:
        - PUNT: (maybe not?) error if room was seen elsewhere on the map
        - DONE: back-connect (bi-directional) if `previous_room` and unbroken line of passage chars
        - DONE: set as `previous_room`
        - DONE: also examine above, follow vertical passage to prior room

- DONE: compile room dict to sm rules

---
