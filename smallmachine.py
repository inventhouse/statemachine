# SmallMachine: Copyright © 2021-2024 Benjamin Holt - MIT License

from collections import deque
import re


def statemachine(state=None, rules=None, history=..., debug=None):
    "Create a StateMachine instance with a ContextTracer and optional verbose debugging tracer with configurable prefix; this is the most common way to set up a machine"

    ctx_args = {"history": history} if history is not ... else {}
    ctx = ContextTracer(**ctx_args)
    tracer = ctx
    if debug or debug == "":
        dbg_args = {"prefix": debug} if isinstance(debug, str) else {}
        dbg = PrefixTracer(**dbg_args)
        tracer = MultiTracer(dbg, ctx)
    fsm = StateMachine(state, rules, tracer=tracer, unrecognized=ctx.reject)
    return fsm, ctx


class StateMachine(object):
    """
    State machine engine that makes minimal assumptions but includes some nice conveniences.

    State is simply the starting state for the machine.

    The rules dictionary maps each state to a list of rule tuples, each of which includes a label, a test, an action, and a destination; more about rule elements in the __call__ documentation.

    Rules associated with the special '...' state are implicitly added to all states' rules, to be evaluated after explicit rules.

    Tracer is an optional callable that takes a tracepoint string and its associated values, and is called at critical points in the input processing to follow the internal operation of the machine.  A simple tracer can produce logs that are extremely helpful when debugging, see PrefixTracer for an example.  Tracepoints are distinct constants which can be used by more advanced tracers for selective verbosity, state management, and other things.  Tracer values can be collected for later use or to provide context for more sophisticated tests or actions; see ContextTracer.  Tracers can be stacked using MultiTracer.

    The unrecognized handler is an optional callable that takes input that did not match any rule in the current state nor the implicitly added rules from the None state.  By default it returns None; setting this to raise makes the machine more strict which can help debugging; using ContextTracer's 'ctx.reject' is particularly good for this.

    Public attributes can be manipulated after init; for example a rule action could set the state machine's tracer to start or stop logging of the machine's operation.
    """
    def __init__(self, state=None, rules=None, tracer=lambda m, **v: None, unrecognized=lambda _: None):
        # rules = { state: [(label, test, action, state), ...], ...}
        self.rules = rules if rules is not None else {}  # Rules can be set after init
        self.state = state
        self.tracer = tracer
        self.unrecognized = unrecognized

    # The formatter keys are all distinct so they can be aggregated with dict.update; see ContextTracer for an example implementation
    TRACE_INPUT = "{state}('{input}')"
    TRACE_RULE = "  {label}: {test} -- {action} --> {dest}"
    TRACE_RESULT = "  {label}: {result}"
    TRACE_RESPONSE = "    {response}"
    TRACE_NEW_STATE = "    --> {new_state}"
    TRACE_UNRECOGNIZED = "\t(No match)"

    def __call__(self, i):
        """
        Tests an input against the rules for the current state plus the global rules from the None state.

        Each rule consists of a label, test, action, and destination, which work as follows:

        - Label: string used for identifying the "successful" rule when tracing.

        - Test: if callable, it will be called with the input, otherwise it will be tested for equality with the input; if the result is truish, the rule succeeds and no other rules are tested.

        - Action: when a test succeeds, the action is evaluated and the response is returned by this call.  If action callable, it will be called with the input; it is common for the action to have side-effects that are intended to happen when the test is met.  If it is not callable, the action literal will be returned.

        - Destination: finally, if destination is callable it will be called with the current state to get the destination state, otherwise the literal value will be the destination.  If the destination state is '...', the machine will remain in the same state (self-transition or "loop".)  Callable destinations can implement state push/pop for recursion, state exit/enter actions, non-deterministic state changes, and other interesting things.
        """
        self.tracer(StateMachine.TRACE_INPUT, state=self.state, input=i)
        rule_list = self.rules.get(self.state, []) + self.rules.get(..., [])
        assert rule_list, "Empty rule list, set tracer to debug"
        for l,t,a,d in rule_list:
            self.tracer(StateMachine.TRACE_RULE, label=l, test=t, action=a, dest=d)
            result = t(i) if callable(t) else t == i
            if result:
                self.tracer(StateMachine.TRACE_RESULT, label=l, result=result)
                response = a(i) if callable(a) else a
                self.tracer(StateMachine.TRACE_RESPONSE, response=response)
                dest = d(self.state) if callable(d) else d
                self.tracer(StateMachine.TRACE_NEW_STATE, new_state=dest)
                if dest is not ...:
                    assert dest in self.rules, f"Unknown state '{dest}', set tracer to debug"
                    self.state = dest
                return response
        else:
            self.tracer(StateMachine.TRACE_UNRECOGNIZED)
            return self.unrecognized(i)
#####


###  Tracing  ###
def PrefixTracer(prefix="T>", printer=print):
    "Prints tracepoints with a distinctive prefix and, optionally, to a separate destination than other output"
    def t(tp, **vals):
        printer(f"{prefix} {tp.format(**vals)}")
    return t


def MultiTracer(*tracers):
    "Combines multiple tracers"
    def mt(tp, **vals):
        for t in tracers:
            t(tp, **vals)
    return mt


class ContextTracer(object):
    """Collects the context and history of a StateMachine as it evaluates an input; use the ctx.throw bound method to raise ValueError with a context history trace on unrecognized input.

    ContextTracer attributes are added and updated as the machine processes as follows:

    Input received:
    - tracepoint: The current tracepoint, updated at each step
    - state: The current state
    - input: The raw input
    - input_count: The count of inputs received, the first input is 1

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
        if tracepoint == StateMachine.TRACE_INPUT:
            self.input_count += 1
            values["input_count"] = self.input_count
            self.context = values
        else:
            if tracepoint == StateMachine.TRACE_UNRECOGNIZED:
                values["unrecognized"] = StateMachine.TRACE_UNRECOGNIZED.strip()
            self.context.update(values)

        if self.compact and tracepoint == StateMachine.TRACE_NEW_STATE:
            self.fold_loop()
        if tracepoint in (StateMachine.TRACE_NEW_STATE, StateMachine.TRACE_UNRECOGNIZED):
            self.history.append(self.context)

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

    ## Handle unrecognized
    def reject(self, i):
        """Raises a `ValueError` for an unrecognized input to a `StateMachine` with a trace of that machine's recent significant transitions."""
        ctx = self.context
        trace_lines = "\n".join(self.format_trace())
        s = ctx.get("state", "State missing")
        i = ctx.get("input", "Input missing")
        c = ctx.get("input_count", "Count missing")
        msg = f"Unrecognized input\nStateMachine Traceback (most recent transition last):\n{trace_lines}\nValueError: '{s}' did not recognize {c}: '{i}'"
        raise ValueError(msg)

    ## Formatting
    def format_transition(self, t):
        tp = t.get("tracepoint", "Tracepoint missing")
        if tp == StateMachine.TRACE_NEW_STATE:
            # Most transitions will be "complete"
            looped = "    ({loop_count} loops in '{state}' elided)\n".format_map(t) if "loop_count" in t else ""
            return looped + "{input_count}: {state}('{input}') > {label}: {result} -- {response} --> {new_state}".format(**t)
        if tp == StateMachine.TRACE_UNRECOGNIZED:
            # Unrecognized has its own format
            return "{input_count}: {state}('{input}') > No match".format(**t)
        return f"PARTIAL: {str(t)}"  # If transition somehow did not complete but also is not unrecognized, simply dump it for debugging

    def format_trace(self):
        return [ self.format_transition(t) for t in self.history ]
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
