Statemachine Line EDitor
========================
or: Sed-Like EDitor
-------------------
A bit like [`sed`](https://en.wikipedia.org/wiki/sed) but uses statemachine-based rules to create line-based filters and transducers.

Neat!  But why not just use `sed`?  Sure, go for it, it's one of the great utilities.  This works _**very**_ differently, and I make no claims that it is better or easier.  It was _a ton_ of fun to write, though, and it uses modern Python regular expressions and formatting, which I like, and offers output styling like colors and bold.

`sled` is a front-end on a general-purpose engine, [`statemachine`](statemachine.py); it defines just a few simple tests and actions for filtering and transforming lines of text, but if we need more, we can always move up to Python with the full power and flexibility of `statemachine`.

In these parsers, "states" serve to group the rules to apply to input; rules can filter or transform input, transition between states (and, thus, rule-sets), or both.  Together states and rules build the logic for both navigating and processing the input stream and transforming it into an output stream.


Overview
--------
Our parsers will be defined by rules that start from a state, and based on a test, move to a destination state ("dst") and may perform an action the result of which is the output of the parser; rules are also allowed to have a "tag" to aid in tracing and debugging.

Rules with no starting state will be added to all states, but are evaluated after all explict rules; rules with no "dst" remain in the same state ("self-transition").

If an input does not match any rule for the current state, an exception is raised with a short trace of recent transitions; the depth of this trace can be set or additional tracing can be enabled with `-t/--trace`.

Named rules can be defined with `-r/--named-rules` and start with a (non-whitespace) delimiter character of our choice follwed by 7 fields:

    :name:test:arg:dst:action:arg:tag

Rules are added to states in the underlying statemachine with `-a/--add-rules`, and may be either named or anonymous:

    :state:name:tag
    :state:test:arg:dst:action:arg:tag

For convenience, unnecessary fields may be omitted from the end in all cases, 'test' and 'action' commands are not case-sensitive, and named rules will be automatically tagged.

In addtion to the general options and help that can be printed with `-h/--help`, available tests and actions are documented in `--more-help` and text styling is shown in `--style-help`.

`F`ormat and `S`ub actions have a few automatic placeholders:
- `{i}` contains the original input string
- `{r}` contains the test result; if this is a `match` object, captured groups are available as items, like `{r[G]}`.  Note that in the `S`ub action, you probably want to use [`re.sub`'s backreferences](https://docs.python.org/3/library/re.html#re.sub) instead of `r`
- `{s}` offers text styling and colors as attributes; don't forget to return the terminal to normal with `{s.off}`!  Note that formatting only applies to terminal output and is not emitted when the output is being piped or redirected.


A detailed example
------------------
This example will use the `status.txt` file, a sanitized version of the output from a team status chatbot.  Throughout the example, we'll use the `:` delimiter as a convention, but each rule can be defined with any non-whitespace character that doesn't otherwise appear in the rule.

### Pass lines between delimiters

Let's get the lines from `@bholt` to the next `@`-name line; for this we'll need a few named rules, defined with `-r/--named-rules`:

- **AtBholt** - `M`atch lines starting with `@bholt`, move to the `bholt` state, and `F`ormat the `i`nput `b`old and `blue`, with no tag (the last empty field could simply be skipped, which we will do with the rest of the examples):

    `:AtBholt:M:@bholt:bholt:F:{s.b}{s.blue}{i}{s.off}:`

- **AtOther** - `M`atch lines starting with `@`, move to the `start` state, and no action will drop the line so we leave off the rest of the fields:

    `:AtOther:M:@:start`

- **PassAll** - `T`rue will accept any line and takes no argument, no "dst" will simply remain in the same state, and pass the `I`nput is the action:

    `:PassAll:T:::I`

- **DropAll** - `T`rue accepts any line, no "dst" will remain in the same state, and no action will drop the input:

    `:DropAll:T`

Now we combine these into a state machine with `-a/--add-rules`.  `start` tries the `AtBholt` rule (which could transition to the `bholt` state), then falls-back to `DropAll`, on the other hand the `bholt` state checks `AtOther` (which transitions back to `start`) and otherwise does `PassAll`:

```
> cat status.txt | ./sled -r ":AtBholt:M:@bholt:bholt:F:{s.b}{s.blue}{i}{s.off}:" ":AtOther:M:@:start" ":PassAll:T:::I" ":DropAll:T" -a ":start:AtBholt" ":start:DropAll" ":bholt:AtOther" ":bholt:PassAll"
@bholt
Set up the stuff for JIRA-123, but was unable to test it
some more
lines to see
multiline status
@bholt
Work with @abc on her front-end work, and continue trying to fix my development environment
@bholt
JIRA-123 is very close to ready
@bholt
Project won't build for me and others, cause is unknown
5. Is there anything you would like to discuss with the team?
<no response>
I didn't hear from @qed, @foo, @bar, @qux! Keep up your good work team!
```

This could also be done with anonymous rules, as each rule was only added in one place in this example; named rules do have the advantage of automatic tagging to make trace output easier to understand, however.

### Tracing

Statemachines are powerful and fascinating - and can be hard to debug if we can't see what they're doing sometimes.

Try adding `-t` to see a _very_ detailed trace as the parser tries each rule.  All trace lines start with the prefix `T> ` by default; normal output lines are interspersed without a prefix.

For each input, the trace prints the current state as a banner, followed by the input count and the input itself; then as each transition is tried, a line is printed with the tag (if any), the test result, and a left-arrow followed the detailed rule.  The last of these lines will have a truish test result and will be followed by the state transition and output of the rule's action.  Here are the first couple frames of the example above:

```
T> 
T> =====  start  =====
T> 1: 1. What did you do yesterday?
T>      [AtBholt] None <-- (start, <function matchTest.<locals>.c at 0x10ee7b9d8>, <function inputAction at 0x10ee7a6a8>, bholt)
T>      [DropAll] True <-- (start, <function trueTest at 0x10ee7a048>, None, None)
T>          start --> start
T>          ==> 'None'
T> 
T> =====  start  =====
T> 2: @bholt
T>      [AtBholt] <re.Match object; span=(0, 6), match='@bholt'> <-- (start, <function matchTest.<locals>.c at 0x10ee7b9d8>, <function inputAction at 0x10ee7a6a8>, bholt)
T>          start --> bholt
T>          ==> '@bholt'
@bholt
```

Note the very last line above has no prefix, it is the parser's normal output.

### Unrecognized input

Perhaps we just want the first set of `@bholt` lines so we define the `AtOther` rule to take the parser to an `end` state, like this:

    `:AtOther:M:@:end`

Uh-oh!  We didn't add any rules to the `end` state, so the parser doesn't know what to do with input and throws a `ValueError`, _but_ after the regular Python trace, it prints an abbreviated statemachine trace:

```
Traceback (most recent call last):
  File "./sled", line 260, in <module>
    xit = main(sys.argv, os.environ, sys.stdin)
  File "./sled", line 116, in main
    for line in parser.parse( l.rstrip("\n") for l in stdin ):
  File "/Users/bjh/inventhub/statemachine/statemachine.py", line 147, in parse
    out = self.input(i)
  File "/Users/bjh/inventhub/statemachine/statemachine.py", line 141, in input
    return super().input(i)
  File "/Users/bjh/inventhub/statemachine/statemachine.py", line 61, in input
    return self.unrecognized(i, self.state, self.i_count)
  File "/Users/bjh/inventhub/statemachine/statemachine.py", line 269, in throw
    raise ValueError(msg)
ValueError: Unrecognized input
StateMachine Traceback (most recent transition last):
  1: 1. What did you do yesterday?
      (2 tested) [DropAll] True <-- (start, <function trueTest at 0x10ebaaf28>, None, None)
          start --> start
          ==> 'None'
  2: @bholt
      (1 tested) [AtBholt] <re.Match object; span=(0, 6), match='@bholt'> <-- (start, <function matchTest.<locals>.c at 0x10ebb39d8>, <function inputAction at 0x10ebb2620>, bholt)
          start --> bholt
          ==> '@bholt'
  ...(Looped 4 times)
  6: multiline status
      (2 tested) [PassAll] True <-- (bholt, <function trueTest at 0x10ebaaf28>, <function inputAction at 0x10ebb2620>, None)
          bholt --> bholt
          ==> 'multiline status'
  7: @def
      (1 tested) [AtOther] <re.Match object; span=(0, 1), match='@'> <-- (bholt, <function matchTest.<locals>.c at 0x10ebb3ae8>, None, end)
          bholt --> end
          ==> 'None'
ValueError: 'end' did not recognize 8: 'debugged things'
```

This shows us the state and which input it did not recognize and a bit about how it got there.  The depth of this trace is 5 by default, but can be adjusted by passing an integer to `-t/--trace`.

For convenience, `-d/--drop-all` and `-p/--pass-all` can add a catch-all rule for us.


Rules files
-----------
Entering all these rules on the command-line can be tedious and without comments or other context, could be very hard to understand again.  Thus, we can get rules from a file with `-f/--rules-file`.

Rules are parsed from within blocks marked with `Named Rules:` and `Add Rules:` lines and a block can be closed with `End Rules`; any content outside the blocks is ignored.  `#`-style comments are also ignored, though `#` can be escaped by doubling; see [`statusparser.sled`](statusparser.sled) for some examples of how the rules are parsed.  We can run the example like this:

`> cat status.txt | ./sled -f statusparser.sled`

All the `Named Rules:` and `Add Rules:` blocks will be coalesced so the named rules will be available to all add rules commands even if they were defined later in the file.

Additionally, rules named on the command-line can override ones defined in the file and any added on the command-line will have higher precedence.  For example, to dimly see all the lines that the `DropAll` rule would've dropped, we can run:

`> cat status.txt | ./sled -f statusparser.sled -r ":DropAll:T:::F:{s.dim}D> {i}{s.off}"`

(Note that some lines are handled by other rules, so this doesn't actually show every dropped line.)


To Do
-----
- "intro to statemachines" - maybe as a separate tutorial?  or statemachine.md?
- pull styling out into its own importable module
- `--styled` to force styling even when piped

- change trace to take a format so we can use things like `{s.dim}`
- wrap `--more-help` - hard to make this right

- generalize comment stripper to take a string like `//`, `;`, or `--`

- HTML escaping and styling?

- input file(s) instead of stdin

- Error action?  fire the unrecognized handler deliberately
    - would need a reference to the sm, not sure how to do that right now

- named tests & actions?
- good way to allow multiple actions to apply to a line

- NO: fold DSL into main statemachine? - unless I figure a better way to do tests and actions than hardcoded maps, just no.
    - maybe hoist some of the tests or actions, though

### Doneyard

- DONE: parse instructions into rules
    - DONE: work out tests and actions to offer
        - DONE: string, re.match, input number gte, trueTest
        - DONE: string, input action, format action, None action
        - DONE: Search test
        - DONE: Sub action that does a full replace-all-occurences
    - DONE: named rules
        - DONE: auto-tag with name if no tag is specified
    - PUNT: make delim escape-able

- DONE: run lines through SM

- DONE: help for tests and actions - kinda bolted-on

- DONE: add extras
    - DONE: `-p/--pass-all`, `-d/--drop-all` to add pass/drop-by-default rule
    - PUNT: lenient vs. "strict"
    - DONE: Full trace with prefix flag

- DONE: rules file
    - DONE: read rules file, and gross parse stripping #-style comments and create named list and rules list
    - DONE: command rules should override file rules
        - DONE: thus parse those, parse file named rules but update with named_rules, then parse file rules and append to command rules before adding
    - DONE: comments
    - DONE: ignore surrounding junk (allow rules to be embedded in other content)

- PUNT: maybe add sed-ish versions of some basic things
- PUNT: maybe a `-m/--match-and-format` "simple" version that assumes test is `match` and action is `format` and just takes the args
    - `-e/--sed-expression`, `-m/--match-and-format`, and `-a/--add-rules` would be mutually exclusive

- DONE: color, bold, etc style formatting
    - DONE: steal tput from `allgit`
    - NO: or could just hardcode ansi codes - ick
    - DONE: formatting for `S`ub action
    - DONE: `--style-help`
        - DONE: wrap style help - good 'nuff
    - DONE: Docs & examples

- DONE: `-c/--strip-comments` convenience rule to make stripping `#`-style comments easy
    - DONE: no good mechanism to make it an explicit rule on all states, would have to be lower-priority implicit rule (could pre-process with a separate invocation and make it a named rule that could be explicitly added without needing to define it)
    - PUNT: document somewhere other than `-h`?

- DONE: case-insensitive match and search actions
    - PUNT: any other flags?

---
