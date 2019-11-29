#!/usr/bin/env python3
# Copyright (c) 2019 Benjamin Holt -- MIT License

"""General-purpose state machine engine with extras and tracing."""


from collections import deque, namedtuple
import re
#####


###  State Machine Core  ###
# Note: For clarity, we will refer to the edges of a state diagram as "rules" and the _operation_ of those rules as "transitions"
TransitionInfo = namedtuple("TransitionInfo", ("state", "dst", "count", "result"),)
TraceInfo = namedtuple("TraceInfo", ("t_info", "test", "action", "tag", "out", "end"))


class StateMachineCore(object):
    """State machine engine that makes minimal, but convenient, assumptions.

    StateMachineCore holds the primary implementation separate from the extras for clarity, but is not meant to be used directly; see StateMachine for full documentation.
    """
    def __init__(self, start):
        """Creates a state machine in the start state."""
        self.rules = {start:[], None:[],}  # {state: [(test, dst, action, tag), ...], ...}
        self.state = start
        self.i_count = 0

        # Baseline both tracer and unrecognized handler to no-ops
        self.tracer = lambda *_: None
        self.unrecognized = lambda *_: None


    def add(self, state, test, dst, action=None, tag=None):
        """Add rule from `state` to `dst` if `test`, with optional `action`, and debugging `tag`.  Rules will be tested in the order they added."""
        if state not in self.rules:
            self.rules[state] = []
        if dst not in self.rules:
            self.rules[dst] = []
        self.rules[state].append((test, dst, action, tag))  # REM: auto-tag "global" rules?


    def input(self, i):
        """Tests input `i` against current state's rules, changes state, and returns the output of the first matching rule's action."""
        self.i_count += 1
        rlist = self.rules.get(self.state, [])
        for (test, dst, action, tag) in rlist + self.rules.get(None, []):  # Rules starting from None are added to all states
            t_info = TransitionInfo(self.state, dst, self.i_count, None)
            result = test(i, t_info) if callable(test) else test == i
            t_info = t_info._replace(result=result)
            if result:
                if dst is not None:  # Transitions ending in None stay in the same state
                    self.state = dst
                # Run the action after the state change so it could override the end state (e.g. pop state from a stack)
                out = action(i, t_info) if callable(action) else action
                # Be sure to trace the actual end state after `action` is done
                self.tracer(i, TraceInfo(t_info, test, action, tag, out, self.state))
                return out
            self.tracer(i, TraceInfo(t_info, test, action, tag, None, self.state))

        return self.unrecognized(i, self.state, self.i_count)
#####


###  State Machine  ###
class StateMachine(StateMachineCore):
    """State machine engine that makes minimal, but convenient, assumptions.

    This is a stripped-down [Mealy](https://en.wikipedia.org/wiki/Mealy_machine) (output depends on state and input) state machine engine.  Good for writing parsers, but makes no assumptions about text parsing, and doesn't have any unnecessary requirements for the states, tests, or actions that form the rules that wire up the machines it can run.
    """
    def __init__(self, start, tracer=True, unrecognized=True):
        """Creates a state machine in the start state with an optional tracer and unrecognized input handler.

        An optional `tracer` gets called after each rule tested with the input and a `TraceInfo`.  By default, this uses `RecentTracer` to collect the last five significant transitions (self-transitions are counted but only the last of them is kept) to be raised by the default `unrecognized` handler.  An integer can be passed to set the trace depth (or unlimited if negative).  This can be set to another callable, such as a `Tracer` instance, for a complete, quite verbose, log of the operation of your state machine; the recent trace will still be collected if the default unrecognized handler is being used.

        If an input does not match any rule the `unrecognized` handler is called with the input, state and input count.  By default this raises a `ValueError` with a short trace of recent transitions.  It can be set to `False` to disable the default tracing and ignore unrecognized input.
        """
        super().__init__(start)

        # Add trace and unrecognized handlers
        if callable(tracer):
            self.tracer = tracer
        if callable(unrecognized):
            self.unrecognized = unrecognized

        if unrecognized is True:
            # Use default tracer and unrecognized handler
            traceDepth = 5  # Each transition prints 4-5 lines of trace
            if type(tracer) == int:
                traceDepth = tracer
            rt = RecentTracer(depth=traceDepth)
            self.unrecognized = rt.throw
            self.tracer = rt
            if callable(tracer):
                # If another tracer was specified, use both of them
                def both(i, t):
                    tracer(i, t)
                    rt(i, t)
                self.tracer = both


    def add(self, state, test, dst, action=None, tag=None):
        """Add rule from `state` to `dst` if `test`, with optional `action`, and debugging `tag`.  Rules will be tested in the order they added.

        `state` and `dst` must be hashable; if `state` is `None`, this rule will be implictly added to all states, and evaluated after any explict rules.  If `dst` is `None`, the machine will remain in the same state (self-transition) or the action could directly set a dynamic state.

        If `test` is callable, it will be called as described for the `input` method below, otherwise it will be compared against the input (`test == input`)

        If `action` is callable, it will be called as described for the `input` method below, otherwise it will be returned when the transition is followed.
        """
        super().add(state, test, dst, action=action, tag=tag)


    def build(self, state, *rules):
        """Add several rules to a state.

        Remaining arguments for rules can be given as any combination of:
        - *args-compatible tuple like (test, dst, action)
        - **kwargs-compatible dict like {"test": test, "dst": dst, "action": action}
        - or a pair, one of each, like ((test, dst), {"action": action})
        """
        for r in rules:
            if type(r) == dict:
                self.add(state, **r)
            elif [ type(i) for i in r ] == [tuple, dict]:
                args, kwargs = r
                self.add(state, *args, **kwargs)
            else:
                self.add(state, *r)


    def input(self, i):
        """Tests input `i` against current state's rules, changes state, and returns the output of the first matching rule's action.

        Rules are tested in the order they were added to their originating state and the first one with a truish result is followed.  Rules starting from `None` are implicitly added to all states and evaluated in order after the current state's explict rules.

        If `test` is callable, it will be called with the input and a `TransitionInfo`; a truish result will cause the machine will go to `dst` and this rule's action to be called.  If `test` is not callable will be compared against the input (`test == input`).

        If the test result is truish and `action` is callable, it will be called with the input and a `TransitionInfo` and the output will be returned.  Otherwise, the `action` itself will be returned when the transition is followed.
        """
        return super().input(i)


    def parse(self, inputs):
        "Feeds items from the `inputs` iterable into the state machine and yields non-None outputs"
        for i in inputs:
            out = self.input(i)
            if out is not None:
                yield out
#####


###  Tests  ###
def trueTest(i, _):
    "Always returns `True`"
    return True


def inTest(l):
    "Creates a test closure that returns true if an input is in `l`"
    def c(i, _):
        return i in l
    return c


def anyTest(l):
    "Creates a test closure that returns the first truish result of the tests in `l`"
    def c(i, t):
        for test in l:
            r = test(i, t)
            if r:
                return r
        return False
    return c


def matchTest(pattern):
    "Creates a test closure that returns true if an input matches `pattern` using `re.match`"
    r = re.compile(pattern)
    def c(i, _):
        return r.match(i)
    return c
#####


###  Actions  ###
def inputAction(i, _):
    """Returns the input that matched the transition"""
    return i
#####


###  Utilities  ###
def format_rule_table(sm):
    """TODO: impliment this"""
    pass
#####


###  Tracing  ###
class Tracer():
    """Collects a trace of state machine transitions (or not) by input."""
    def __init__(self, printer=print):
        """Creates a Tracer instance with a `printer` callback for lines of trace output.

        The instance is callable and can be used directly as the `tracer` callback of a `StateMachine`.  The `printer` is expected to add newlines or otherwise separate each line output; a prefix can be added to each line like this: `printer=lambda s: print(f"T: {s}")`"""
        self.input_count = 0
        self.printer = printer


    def __call__(self, i, t):
        """Processes a tracer callback from a `StateMachine` instance, pushing each line of output to the `printer` callback."""
        (t_info, test, action, tag, out, end) = t
        if t_info.count != self.input_count:
            # New input, start a new block, number and print it
            self.input_count = t_info.count
            self.printer("")
            self.printer(f"=====  {t_info.state}  =====")
            self.printer(f"{t_info.count}: {i}")

        # Format and print tested transition
        t_string = f"\t[{tag}] " if tag else "\t"
        t_string += f"{t_info.result} <-- ({t_info.state}, {test}, {action}, {t_info.dst})"
        self.printer(t_string)

        if t_info.result:
            # Transition fired, print state change and output
            self.printer(f"\t    {t_info.state} --> {end}")
            self.printer(f"\t    ==> '{out}'")


class RecentTracer(object):
    """Keeps a limited trace of significant state machine transitions to provide a recent "traceback" particularly for understanding unrecognized input.

    Only "successful" transitions are recorded, and if a transition stays in the same state, those are counted but only the last is retained."""
    def __init__(self, depth=10):
        """Creates a RecentTracer instance with trace depth.

        The instance is callable and can be used directly as the `tracer` callback of a `StateMachine`, likewise the `throw` method can be used as the `unrecognized` callback (and both are used default)."""
        if depth < 0:
            depth = None  # Unlimited depth
        self.buffer = deque(maxlen=depth)  # [(t_info, (loop_count, t_count, i_count)), ...]
        self.t_count = 0  # Count of tested transitions since the last one that was followed


    def __call__(self, i, t):
        """Processes a tracer callback from a `StateMachine` instance."""
        (t_info, *_) = t
        self.t_count += 1
        if not t_info.result:
            return

        loop_count = 1
        if len(self.buffer):
            (_, ((s, *_), *_), (lc, *_)) = self.buffer[-1]  # FIXME: this kind of unpacking is out of control
            if t_info.state == s and (t_info.state == t.end):
                # if the state isn't changing, bump the loop count and replace the last entry
                loop_count = lc + 1
                self.buffer.pop()

        self.buffer.append((i, t, (loop_count, self.t_count)))
        self.t_count = 0


    def throw(self, i, s, c):
        """Raises a `ValueError` for an unrecognized input to a `StateMachine` with a trace of that machine's recent significant transitions."""
        traceLines = "\n".join(self.formatTrace())
        msg = f"Unrecognized input\nStateMachine Traceback (most recent transition last):\n{traceLines}\nValueError: '{s}' did not recognize {c}: '{i}'"
        raise ValueError(msg)


    def formatTrace(self):
        """Formats the recent significant transitions into a list of lines for output."""
        trace = []
        for (ti, (t_info, test, action, tag, out, end), (lc, tc)) in self.buffer:  # FIXME: this kind of unpacking is out of control
            if lc > 1:
                trace.append(f"  ...(Looped {lc} times)")
            trace.append(f"  {t_info.count}: {ti}")
            t_string = f"      ({tc} tested) "
            if tag:
                t_string += f"[{tag}] "
            t_string += f"{t_info.result} <-- ({t_info.state}, {test}, {action}, {t_info.dst})"
            trace.append(t_string)
            trace.append(f"          {t_info.state} --> {end}\n          ==> '{out}'")
        return trace
#####


###  Stack Machine  ###
class StackMachine(StateMachine):
    """Stack machine based on the StateMachine engine above."""
    def __init__(self, start, tracer=True, unrecognized=True):
        super().__init__(start, tracer=tracer, unrecognized=unrecognized)  # TODO: may need to augment tracers to include stacks somehow
        self.stacks = {None: deque(),}  # Allow any number of named stacks; default stack is named `None`


    def len(self, stack=None):
        if stack not in self.stacks:
            return 0
        return len(self.stacks[stack])


    def append(self, v, stack=None):
        if stack not in self.stacks:
            self.stacks[stack] = deque()
        self.stacks[stack].append(v)


    def pop(self, stack=None):
        if stack not in self.stacks or len(self.stacks[stack]) < 1:
            return None
        return self.stacks[stack].pop()


    def appendInputAction(self, stack=None):
        def action(i, t_info):
            self.append(i, stack=stack)
            return None
        return action


    def appendResultAction(self, stack=None):
        def action(i, t_info):
            self.append(t_info.result, stack=stack)
            return None
        return action


    def popAction(self, stack=None):
        def action(i, t_info):
            return self.pop(stack=stack)
        return action


    class StateStack(object):
        pass


    def appendStateAction(self, stack=StateStack):  # Use separate "state" stack by default instead of the None ("data") stack
        def action(i, t_info):
            self.append(t_info.state, stack=stack)
            return None
        return action


    def popStateAction(self, stack=StateStack):
        def action(i, t_info):
            self.state = self.pop(stack=stack)
            return None  # Only set the state, no output
        return action
#####


###  Main  ###
if __name__ == "__main__":
    print("Parsed")
#####
