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
    - work out tests and actions to offer
        - string, re.match, re.search, input number gte, trueTest
        - string, input action, format action
    - make delim escape-able
    - rules file?  `#!`?
- run lines through SM
    - stdin or file
- add extras
    - print by default vs. drop by default
    - lenient vs. "strict"
- fold DSL into main statemachine?
- add sed-ish versions of some basic things

### Doneyard


---
