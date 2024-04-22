# SmallMachine: Copyright © 2021-2024 Benjamin Holt - MIT License

from collections import deque
from enum import Enum
import re


__ = object()  # Sentinel for default arguments not to be passed on
def statemachine(rules=__, state=__, debug=False, history=__, checkpoints=__, tracer=None):
    """Create a batteries-included state machine with convenience options.

    Returns a StateMachine pre-configured to reject unknown input and states; this is the most common way to set up a machine.  Optionally it can also have a verbose debugging tracer with configurable prefix added.

    History and checkpoints arguments will be passed on to the CheckpointTracer, see that for details.

    An additional tracer can also be passed in and it will be called before any default tracers.
    """

    tracers = [tracer] if tracer else []
    if debug is not False:
        dbg_args = {"prefix": debug} if debug is not True else {}
        dbg = PrefixTracer(**dbg_args)
        tracers.append(dbg)

    checkpoints_args = {} if checkpoints is __ else {"checkpoints": checkpoints}
    history_args = {} if history is __ else {"history": history}
    tracers.append(CheckpointTracer(**checkpoints_args, **history_args))
    tracer = MultiTracer(*tracers) if len(tracers) > 1 else tracers[0]
    state_args = {} if state is __ else {"state": state}
    rules_args = {} if rules is __ else {"rules": rules} 
    return StateMachine(**rules_args, **state_args, tracer=tracer)
#####


###  Test Helpers  ###
class match_test(object):
    """Thin wrapper around re.match to format a nice __str__."""
    def __init__(self, test_re_str):
        self.test_re = re.compile(test_re_str)

    def __call__(self, input, **_):
        return self.test_re.match(input)

    def __str__(self):
        return f"'{self.test_re.pattern}'.match(input)"


class search_test(object):
    """Thin wrapper around re.search to format a nice __str__."""
    def __init__(self, test_re_str):
        self.test_re = re.compile(test_re_str)

    def __call__(self, input, **_):
        return self.test_re.search(input)

    def __str__(self):
        return f"'{self.test_re.pattern}'.search(input)"


class in_test(object):
    """Callable to test if input is in a collection and format a nice __str__."""
    def __init__(self, in_list):
        self.in_list = in_list

    def __call__(self, input, **_):
        return input in self.in_list

    def __str__(self):
        return f"input in {self.in_list}"
#####


###  Action Helpers  ###
class pretty_action:
    """Decorator to wrap an action callable and give it a nice __str__; not needed if an action already prints nicely"""
    def __init__(self, action):
        self.action = action

    def __call__(self, *args, **kwds):
        # FIXME: this doesn't properly wrap the way functools.wraps does
        return self.action(*args, **kwds)

    def __str__(self):
        return f"{self.action.__name__}(**ctx)"
#####


###  State Machine Core  ###
class Tracepoint(Enum):
    """Defines the tracepoints of the StateMachine core.

    Tracepoints are used to signal a machine's tracer at critical points in the input processing to follow its internal operation.  The formatter keys are all distinct so they can be aggregated with dict.update to build up context as evaluation progresses; StateMachine itself does this, or see CheckpointTracer for an advanced example.
    """
    INPUT = "{input_count}: {state}('{input}')"
    NO_RULES = "\t(No rules: {state})"  # Consider raising NoRulesError
    RULE = "  {label}: {test} -- {action} --> {dest}"
    RESULT = "  {label}: {result}"
    RESPONSE = "    {response}"
    NEW_STATE = "    --> {new_state}"
    UNRECOGNIZED = "\t(No match: '{input}')"  # Consider raising UnrecognizedInputError
    UNKNOWN_STATE = "\t(Unknown state: {new_state})"  # Consider raising UnknownStateError


class StateMachine(object):
    """A state machine engine that makes minimal assumptions but includes some nice conveniences and powerful extensibility.
    """

    def __init__(self, rules=None, state=..., tracer=None):
        """Create a state machine instance which can be called with input and returns output from evaluating the rules for the current state.

        The rules dictionary maps each state to a list of rule tuples, each of which includes a label, a test, an action, and a destination; more about rule elements in the __call__ documentation.

        Rules associated with the special ... (Ellipsis) state are implicitly added to all states' rules, and evaluated after explicit rules.

        State is simply the starting state for the machine; it defaults to the first state defined in the rules or None which is not a special value, it is simply a (possibly) valid state.

        Tracer is an optional callable that takes a Tracepoint and its associated values; it is called at critical points in the input processing to follow the internal operation of the machine.  A simple tracer can produce logs that are extremely helpful when debugging, see PrefixTracer for an example.  Tracepoints are distinct constants which can be used by more advanced tracers for selective verbosity, raising errors for unrecognized input or states, and other things.  Tracers can be stacked using MultiTracer.
        """
        # Starting rules and state can be set after init, but really should be set before using the machine
        # rules dict looks like { state: [(label, test, action, new_state), ...], ...}
        self.rules = rules if rules is not None else {}
        if state is ...:
            state = next(iter(self.rules), None)
        self.state = state
        self.tracer = tracer
        self.context = {}
        self._input_count = 0

    def _trace(self, tp, **vals):
        """Updates the context and calls an external tracer if one is set."""
        self.context["tracepoint"] = tp
        self.context.update(vals)
        if self.tracer:
            self.tracer(tp, **vals)

    def __call__(self, input):
        """Tests an input against the explicit rules for the current state plus the implicit rules from the ... (Ellipsis) state.

        As the rules are evaluated, a context dictionary is built; these keys and values are available to callable rule components as keyword arguments.  Context arguments available when rules are evaluated are: input, input_count, state, and elements of the currently evaluating rule: label, test, action, and dest.

        Each rule consists of a label, test, action, and destination, which work as follows:

        - Label: string used for identifying the "successful" rule when tracing.

        - Test: if callable, it will be called with context arguments, otherwise it will be tested for equality with the input; if the result is truish, the rule succeeds and no other rules are tested and the result is added to the context.

        - Action: when a test succeeds, the action is evaluated and the response is added to the context and returned by this call.  If action callable, it will be called with context arguments, including 'result' from the test above; it is common for the action to have side-effects that are intended to happen when the test is met.  If it is not callable, the action literal will be the response.

        - Destination: finally, if destination is callable it will be called with context arguments, including 'result' and 'response' above, to get the destination state, otherwise the literal value will be the destination.  If the destination state is '...', the machine will remain in the same state (self-transition or "loop".)  Callable destinations can implement state push/pop for recursion, state exit/enter actions, non-deterministic state changes, and other interesting things.
        """
        self.context = {}
        self._input_count += 1
        self._trace(Tracepoint.INPUT, input_count=self._input_count, state=self.state, input=input)
        rule_list = self.rules.get(self.state, []) + self.rules.get(..., [])
        if not rule_list:
            self._trace(Tracepoint.NO_RULES, state=self.state)
        for l,t,a,d in rule_list:
            self._trace(Tracepoint.RULE, label=l, test=t, action=a, dest=d)
            result = t(**self.context) if callable(t) else t == input
            if result:
                self._trace(Tracepoint.RESULT, label=l, result=result)
                response = a(**self.context) if callable(a) else a
                self._trace(Tracepoint.RESPONSE, response=response)
                dest = d(**self.context) if callable(d) else d
                self._trace(Tracepoint.NEW_STATE, new_state=dest)
                if dest is not ...:
                    if dest not in self.rules:
                        self._trace(Tracepoint.UNKNOWN_STATE, new_state=dest)
                    self.state = dest
                return response
        else:
            self._trace(Tracepoint.UNRECOGNIZED, input=input)
            return None
#####


###  Exceptions  ###
class NoRulesError(RuntimeError):
    """Raised when when the current state has no explicit or implicit rules."""
    @classmethod
    def checkpoint(cls):
        def check(tracepoint, **ctx):
            if tracepoint == Tracepoint.NO_RULES:
                return "'{state}' does not have any explicit nor implicit rules".format(**ctx)

        return (check, cls)


class UnrecognizedInputError(ValueError):
    """Raised when input is not matched by any explicit or implicit rule in the current state."""
    @classmethod
    def checkpoint(cls):
        def check(tracepoint, **ctx):
            if tracepoint == Tracepoint.UNRECOGNIZED:
                return "'{state}' did not recognize {input_count}: '{input}'".format(**ctx)

        return (check, cls)


class UnknownStateError(RuntimeError):
    """Raised when a machine transitions to an unknown state."""
    @classmethod
    def checkpoint(cls):
        def check(tracepoint, **ctx):
            if tracepoint == Tracepoint.UNKNOWN_STATE:
                return "'{new_state}' is not in the ruleset".format(**ctx)

        return (check, cls)
#####


###  Tracing  ###
def PrefixTracer(prefix="T>", printer=print):
    """Prints tracepoints with a distinctive prefix and, optionally, to a separate destination than other output"""
    def t(tp, **vals):
        msg = f"{prefix} {tp.value.format(**vals)}" if prefix else tp.value.format(**vals)
        printer(msg)
    return t


class MultiTracer:
    """Combines multiple tracers; tracers list can be manipulated at any time to add or remove tracers."""
    def __init__(self, *tracers):
        self.tracers = list(tracers)

    def __call__(self, tp, **vals):
        for t in self.tracers:
            t(tp, **vals)


class CheckpointTracer(object):
    """Tracer that can check a wide variety of conditions and raise an error if one is met.

    By default, it checks for and raises NoRulesError, UnrecognizedInputError, and UnknownStateError, but can be customized with additional checkpoints.  It also keeps a history of transitions and can (and does by default) compact loops in the trace history by tracking the number of transitions within a state, but retaining only the most recent.

    When it raises an error, it will include a traceback of the recent transitions, similar to a standard stack trace; this is extremely helpful for debugging.
    """

    DEFAULT_CHECKPOINTS = (
        NoRulesError.checkpoint(), 
        UnrecognizedInputError.checkpoint(), 
        UnknownStateError.checkpoint(),
    )

    def __init__(self, checkpoints=(...,), history=10, compact=True):
        """Create a CheckpointTracer with customizable checkpoints, history depth, and compaction.

        Checkpoints is a list of tuples, each with a callable check function and an exception class to raise if the check function returns a message.  If ... (Ellipsis) is in checkpoints, the default checks will be inserted at that point in the list.  Defaults to check for the most common issues: NoRulesError, UnrecognizedInputError, and UnknownStateError.

        History is the number of previous transitions to keep in memory for context; if history is None or negative, the history will be unlimited.  Defaults to 10.

        Compact determines whether the tracer will compact loops in the trace history; if compact is True (default), the tracer will track transitions that remain in the same state, but retain only the most recent and the number of loops will be noted in the traceback.
        """
        if not checkpoints:
            checkpoints = []
        elif ... in checkpoints:
            # Replace ... in checkpoints with the default checkpoints
            checkpoints = list(checkpoints)
            i = checkpoints.index(...)
            checkpoints[i:i+1] = self.DEFAULT_CHECKPOINTS
        self.checkpoints = list(checkpoints)  # List so it can be manipulated later if desired

        self.context = {}  # Simpler to keep our own context than get a reference to the machine
        self.input_count = 0
        if history is None or history < 0:
            history = None  # Unlimited depth
        self.history = deque(maxlen=history)
        self.compact = compact

    ## Collect context & history
    def __call__(self, tracepoint, **values):
        values["tracepoint"] = tracepoint
        if tracepoint == Tracepoint.INPUT:
            if self.context:
                self.history.append(self.context)
            self.input_count += 1
            values["input_count"] = self.input_count
            self.context = values
        else:
            self.context.update(values)

        for check, err in self.checkpoints:
            msg = check(**self.context)
            if msg:
                trace_lines = "\n".join(self.format_trace())
                raise err(f"StateMachine Traceback (most recent last):\n{trace_lines}\n{err.__name__}: {msg}")

        if self.compact and tracepoint == Tracepoint.NEW_STATE:
            self._fold_loop()

    def _fold_loop(self):
        if not self.history:
            return

        latest = self.context
        previous = self.history[-1]
        if previous["state"] == latest["state"]:
            # We have looped
            if "loop_count" in previous:
                # If we are already compacting, fold
                latest["loop_count"] = previous["loop_count"] + 1
                self.history.pop()

            elif len(self.history) >= 2:
                p_previous = self.history[-2]
                if p_previous["state"] == latest["state"]:
                    # Start compacting loops on the third iteration
                    latest["loop_count"] = 2
                    self.history.pop()
                    self.history.pop()

    ## Formatting
    def format_trace(self):
        transitions = (*self.history, self.context)
        return [ self.format_transition(t) for t in transitions ]

    def format_transition(self, t):
        format_parts = (
            ("loop_count", "    ({loop_count} loops in '{state}' elided)\n"),
            ("input", "{input_count}: {state}('{input}')"),
            ("label", " > {label}"),
            ("result", ": {result}"),
            ("response", " -- {response}"),
            ("new_state", " --> {new_state}"),
        )
        fmt = "".join( f for k,f in format_parts if k in t )
        line = fmt.format(**t)
        tp = t.get("tracepoint")
        if tp != Tracepoint.NEW_STATE:
            # Most transitions will finish at NEW_STATE, only annotate ones that don't
            line += f" >> ({tp.name})"
        return line
#####
