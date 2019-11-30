Statemachine Line EDitor
========================
or: Sed-Like EDitor
-------------------
Like `sed` but using consistent statemachine-based rules instead of ad-hoc; maybe with some backwards-compatible(ish) conveniences, though.

`> sled -a :state:test:arg:dst[:action:arg:tag?]`
- first char is delim, can be anything
- that's a lot of fields, can we make some optional? combine the verbs and their args somehow?
- ability to create named rules somehow? -r :name:... then -a :state:rule[:tag?]

Example - print lines from @bholt to the next @-line, suppress others:
`cat status.txt | ./sled -a "::match:@bholt:p:print::" ":p:match:@:start" ":p:True:::print" "::True:::"`

To Do
-----
- parse instructions into rules
    - DONE: work out tests and actions to offer
        - DONE: string, re.match, input number gte, trueTest
        - DONE: string, input action, format action, None action
    - DONE: named rules
    - make delim escape-able
    - rules file?  `#!`?
- DONE: help for tests and actions - kinda bolted-on
- DONE: run lines through SM
    - stdin or file
- add extras
    - PUNT: print by default vs. drop by default
    - PUNT: lenient vs. "strict"
- NO: fold DSL into main statemachine? - unless I figure a better way to do tests and actions than hardcoded maps, just no.
- add sed-ish versions of some basic things
- maybe a `-m/--match-and-format` "simple" version that assumes test is `match` and action is `format` and just takes the args
    - `-e/--sed-expression`, `-m/--match-and-format`, and `-a/--add-rules` would be mutually exclusive

### Doneyard


---
