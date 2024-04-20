# SmallMachine: Copyright © 2021-2024 Benjamin Holt - MIT License

from collections import deque
from enum import Enum
import re


def statemachine(state=None, rules=None, history=..., debug=False, lenient=()):
    """Create a batteries-included state machine with context object.

    Returns a StateMachine and a ContextTracer.  The machine is pre-configured to collect context and reject unknown input and states; this is the most common way to set up a machine.  Optionally it can also have a verbose debugging tracer with configurable prefix added.
    """

    tracers = []
    if debug is not False:
        dbg_args = {"prefix": debug} if debug is not True else {}
        dbg = PrefixTracer(**dbg_args)
        tracers.append(dbg)

    ctx_args = {"history": history} if history is not ... else {}
    ctx = ContextTracer(**ctx_args)  #, lenient=lenient)
    tracers.append(ctx)

    if lenient is not True:
        if NoRulesError not in lenient:
            tracers.append(NoRulesError.tracer())
        if UnrecognizedInputError not in lenient:
            tracers.append(UnrecognizedInputError.tracer())
        if UnknownStateError not in lenient:
            tracers.append(UnknownStateError.tracer())
    tracer = MultiTracer(*tracers) if len(tracers) > 1 else tracers[0]
    fsm = StateMachine(state, rules, tracer=tracer)
    return fsm, ctx


class Tracepoint(Enum):
    # The formatter keys are all distinct so they can be aggregated with dict.update; see ContextTracer for an example implementation
    INPUT = "{state}('{input}')"
    NO_RULES = "\t(No rules: {state})"  # Consider raising NoRulesError
    RULE = "  {label}: {test} -- {action} --> {dest}"
    RESULT = "  {label}: {result}"
    RESPONSE = "    {response}"
    NEW_STATE = "    --> {new_state}"
    UNRECOGNIZED = "\t(No match: '{input}')"  # Consider raising UnrecognizedInputError
    UNKNOWN_STATE = "\t(Unknown state: {new_state})"  # Consider raising UnknownStateError


class StateMachine(object):
    """State machine engine that makes minimal assumptions but includes some nice conveniences.

    State is simply the starting state for the machine.

    The rules dictionary maps each state to a list of rule tuples, each of which includes a label, a test, an action, and a destination; more about rule elements in the __call__ documentation.

    Rules associated with the special '...' state are implicitly added to all states' rules, to be evaluated after explicit rules.

    Tracer is an optional callable that takes a tracepoint string and its associated values, and is called at critical points in the input processing to follow the internal operation of the machine.  A simple tracer can produce logs that are extremely helpful when debugging, see PrefixTracer for an example.  Tracepoints are distinct constants which can be used by more advanced tracers for selective verbosity, state management, raising errors for unrecognized input or states, and other things.  Tracer values can be collected for later use or to provide context for more sophisticated tests or actions; see ContextTracer.  Tracers can be stacked using MultiTracer.

    Public attributes can be manipulated after init; for example a rule action could set the state machine's tracer to start or stop logging of the machine's operation.
    """
    def __init__(self, state=None, rules=None, tracer=lambda tp, **v: None):
        # Starting state and rules can be set after init, but really should be set before using the machine
        self.state = state
        # rules dict looks like { state: [(label, test, action, new_state), ...], ...}
        self.rules = rules if rules is not None else {}
        self.tracer = tracer

    def __call__(self, i):
        """
        Tests an input against the rules for the current state plus the global rules from the None state.

        Each rule consists of a label, test, action, and destination, which work as follows:

        - Label: string used for identifying the "successful" rule when tracing.

        - Test: if callable, it will be called with the input, otherwise it will be tested for equality with the input; if the result is truish, the rule succeeds and no other rules are tested.

        - Action: when a test succeeds, the action is evaluated and the response is returned by this call.  If action callable, it will be called with the input; it is common for the action to have side-effects that are intended to happen when the test is met.  If it is not callable, the action literal will be returned.

        - Destination: finally, if destination is callable it will be called with the current state to get the destination state, otherwise the literal value will be the destination.  If the destination state is '...', the machine will remain in the same state (self-transition or "loop".)  Callable destinations can implement state push/pop for recursion, state exit/enter actions, non-deterministic state changes, and other interesting things.
        """
        self.tracer(Tracepoint.INPUT, state=self.state, input=i)
        rule_list = self.rules.get(self.state, []) + self.rules.get(..., [])
        if not rule_list:
            self.tracer(Tracepoint.NO_RULES, state=self.state)
        for l,t,a,d in rule_list:
            self.tracer(Tracepoint.RULE, label=l, test=t, action=a, dest=d)
            result = t(i) if callable(t) else t == i
            if result:
                self.tracer(Tracepoint.RESULT, label=l, result=result)
                response = a(i) if callable(a) else a
                self.tracer(Tracepoint.RESPONSE, response=response)
                dest = d(self.state) if callable(d) else d
                self.tracer(Tracepoint.NEW_STATE, new_state=dest)
                if dest is not ...:
                    if dest not in self.rules:
                        self.tracer(Tracepoint.UNKNOWN_STATE, new_state=dest)
                    self.state = dest
                return response
        else:
            self.tracer(Tracepoint.UNRECOGNIZED, input=i)
            return None
#####


###  Exceptions  ###
class NoRulesError(RuntimeError):
    "Raised when when a state has no explicit or implicit rules in a StateMachine"
    @classmethod
    def format(cls, **vals):
        sm_trace = trace_helper(cls, vals.get("trace_lines"))
        msg = "{sm_trace}'{state}' does not have any explicit nor implicit rules".format(
            sm_trace=sm_trace,
            **vals
        )
        return msg

    @classmethod
    def tracer(cls, *args, **kwargs):
        return ErrorTracer(Tracepoint.NO_RULES, cls, *args, **kwargs)


class UnrecognizedInputError(ValueError):
    "Raised when input is not matched by any rule in a StateMachine"
    @classmethod
    def format(cls, **vals):
        sm_trace = trace_helper(cls, vals.get("trace_lines"))
        msg = "{sm_trace}'{state}' did not recognize {input_count}: '{input}'".format(
            sm_trace=sm_trace,
            **vals
        )
        return msg

    @classmethod
    def tracer(cls, *args, **kwargs):
        return ErrorTracer(Tracepoint.UNRECOGNIZED, cls, *args, **kwargs)


class UnknownStateError(RuntimeError):
    "Raised when a StateMachine transitions to an unknown state"
    @classmethod
    def format(cls, **vals):
        sm_trace = trace_helper(cls, vals.get("trace_lines"))
        msg = "{sm_trace}'{new_state}' is not in the ruleset".format(
            sm_trace=sm_trace,
            **vals
        )
        return msg

    @classmethod
    def tracer(cls, *args, **kwargs):
        return ErrorTracer(Tracepoint.UNKNOWN_STATE, cls, *args, **kwargs)


def trace_helper(err, trace_lines):
    if not trace_lines:
        return ""
    return f"StateMachine Traceback (most recent last):\n{trace_lines}\n{err.__name__}: "
#####


###  Tracing  ###
def PrefixTracer(prefix="T>", printer=print):
    "Prints tracepoints with a distinctive prefix and, optionally, to a separate destination than other output"
    def t(tp, **vals):
        msg = f"{prefix} {tp.value.format(**vals)}" if prefix else tp.value.format(**vals)
        printer(msg)
    return t


def MultiTracer(*tracers):
    "Combines multiple tracers"
    def mt(tp, **vals):
        for t in tracers:
            t(tp, **vals)
    return mt


class ContextTracer(object):
    """Collects the context and history of a StateMachine as it evaluates an input.

    ContextTracer attributes are added and updated as the machine processes as follows:

    Input received:
    - tracepoint: The current tracepoint, updated at each step
    - state: The current state
    - input: The raw input
    - input_count: The count of inputs received, the first input is 1
    - no_rules: constant "(No rules)" if no explicit nor implicit rules were found for the current state

    Rule evaluation begins:
    - label: The label of the rule being evaluated, usually a name or a distinct tag
    - test: The test callable or literal that will be evaluated
    - action: The action callable or literal that will be evaluated if the test succeeds
    - dest: The destination callable or literal that will define the new state if the test succeeds

    Rule succeeds:
    - result: The result produced by a successful test (e.g. the match object from a regex)

    Action evaluated:
    - response: The value produced by evaluating the action of a successful rule

    Destination evaluated:
    - new_state: The value produced by evaluating the destination of a successful rule
    - unknown_state: constant "(Unknown state)" if the new_state is not in the ruleset

    All rules failed:
    - unrecognized: constant "(No match)"

    Attributes can be tested for with e.g. '"result" in ctx' or retrieved leniently with 'ctx.get("result" [, default])'
    """
    def __init__(self, history=10, compact=True):
        self.context = {}
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
            if tracepoint == Tracepoint.NO_RULES:
                values["no_rules"] = "(No rules)"
            if tracepoint == Tracepoint.UNRECOGNIZED:
                values["unrecognized"] = "(No match)"
            if tracepoint == Tracepoint.UNKNOWN_STATE:
                values["unknown_state"] = "(Unknown state)"
            self.context.update(values)

        if self.compact and tracepoint == Tracepoint.NEW_STATE:
            self.fold_loop()

    def fold_loop(self):
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

    ## Access context
    def get(self, key, default=None):
        return self.context.get(key, default)

    def __contains__(self, key):
        return key in self.context

    def __getattr__(self, attr):
        if attr not in self.context:
            raise AttributeError(f"context currently has no attribute '{attr}'")
        return self.context[attr]

    ## Formatting
    def format_transition(self, t):
        tp = t.get("tracepoint", "Tracepoint missing")
        if tp == Tracepoint.NEW_STATE:
            # Most transitions will be "complete"
            looped = "    ({loop_count} loops in '{state}' elided)\n".format_map(t) if "loop_count" in t else ""
            return looped + "{input_count}: {state}('{input}') > {label}: {result} -- {response} --> {new_state}".format(**t)
        if tp == Tracepoint.NO_RULES:
            # No rules has its own format
            return "{input_count}: {state} > No rules".format(**t)
        if tp == Tracepoint.UNRECOGNIZED:
            # Unrecognized has its own format
            return "{input_count}: {state}('{input}') > No match".format(**t)
        if tp == Tracepoint.UNKNOWN_STATE:
            # Unknown state has its own format
            return "{input_count}: {state}('{input}') > Unknown state: {new_state}".format(**t)
        return f"PARTIAL: {str(t)}"  # If transition somehow does not have a known formatting, simply dump it for debugging  FIXME: do better

    def format_trace(self):
        transitions = (*self.history, self.context)
        return [ self.format_transition(t) for t in transitions ]


class ErrorTracer(object):
    "Raises an error when a tracepoint is called"
    def __init__(self, error_point, error, history=10):
        self.error_point = error_point
        self.error = error
        self.input_count = 0
        self.context = {"input_count": self.input_count}  # REM: do we want configurable context providers?
        if history is None or history < 0:
            history = None  # Unlimited depth
        self.trace = deque(maxlen=history)  # TODO: allow custom trace providers

    def __call__(self, tp, **vals):
        if tp == Tracepoint.INPUT:
            self.input_count += 1
            self.context = {"input_count": self.input_count}
        self.context.update(vals)
        self.trace.append(tp.value.format(**vals))
        if tp == self.error_point:
            msg = self.error.format(
                trace_lines="\n".join(self.trace),
                **self.context
            )
            raise self.error(msg)
#####


###  Test Helpers  ###
class match_test(object):
    "Callable to match input with a regex and format a nice __str__"
    def __init__(self, test_re_str):
        self.test_re = re.compile(test_re_str)

    def __call__(self, i):
        return self.test_re.match(i)

    def __str__(self):
        return f"'{self.test_re.pattern}'.match(i)"


class search_test(object):
    "Callable to search input with a regex and format a nice __str__"
    def __init__(self, test_re_str):
        self.test_re = re.compile(test_re_str)

    def __call__(self, i):
        return self.test_re.search(i)

    def __str__(self):
        return f"'{self.test_re.pattern}'.search(i)"


class in_test(object):
    "Callable to test if input is in a collection and format a nice __str__"
    def __init__(self, in_list):
        self.in_list = in_list

    def __call__(self, i):
        return i in self.in_list

    def __str__(self):
        return f"i in {self.in_list}"
#####
