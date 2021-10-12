# StateMachine: Copyright © 2021 Benjamin Holt - MIT License

# from collections import namedtuple
# Rule = namedtuple("Rule", ("label", "test", "action", "dest"),)

class StateMachine(object):
    """
    Create a state machine instance
    
    The rules dictionary maps each state to a list of rule tuples, each of which includes a label, a test, an action, and a destination; more about rule elements in the call documentation.

    Rules associated with the special None state are implicitly added to all states' rules, to be evaluated after explicit rules.

    State is simply the starting state for the machine.

    Tracer is an optional callable that takes a message and any values to format into it, and is called at critical points in the input processing to produce logs that are extremely helpful when debugging; for example 'lambda msg, **vals: print(msg.format(**vals))'.  Messages are distinct constants which can be used for selective verbosity, among other things.  Tracer values can be collected to print later or provide context for sophisticated tests or actions; see the RecentTracer and ContextTracer for examples.

    The unrecognized handler is an optional callable that takes input that did not match any rule in the current state nor the implicitly added rules from the None state.  By default it returns None; setting this to raise makes the machine more strict which can help debugging: 'def unexpected_input(i): raise ValueError(f"'Input '{i}' did not match, set tracer to debug")'.  Using RecentTracer and setting this to its `.throw` is particularly good for this.

    Public attributes can be manipulated after init; for example a rule action could set the state machine's tracer to start or stop logging of the machine's operation.
    """
    def __init__(self, rules, state, tracer=lambda m, *v: None, unrecognized=lambda _: None):
        self.rules = rules  # { state: [(label, test, action, state), ...], ...}
        self.state = state
        self.tracer = tracer
        self.unrecognized = unrecognized


    # The formatter keys are all distict so they can be aggregated with dict.update; see ContextTracer for an example implementation
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

        - Destination: finally, if destination is callable it will be called with the current state to get the destination state, otherwise the literal value will be the destination.  If the destination state is None, the machine will remain in the same state (self-transition or "loop".)  Callable destinations can implement state push/pop for recursion, state exit/enter actions, non-deterministic state changes, and other interesting things.
        """
        self.tracer(StateMachine.TRACE_INPUT, state=self.state, input=i)
        rule_list = self.rules.get(self.state, []) + self.rules.get(None, [])
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
                if dest is not None:
                    assert dest in self.rules, f"Unknown state '{dest}', set tracer to debug"
                    self.state = dest
                return response
        else:
            self.tracer(StateMachine.TRACE_UNRECOGNIZED)
            return self.unrecognized(i)
#####


###  Tracing  ###
def PrefixTracer(prefix="T>"):
    def t(tp, **vals):
        print(f"{prefix} {tp.format(**vals)}")
    return t


from collections import deque
class RecentTracer(object):
    def __init__(self, depth=10):
        if depth < 0:
            depth = None  # Unlimited depth
        self.transitions = deque(maxlen=depth)
        self.input_count = 0


    def __call__(self, tracepoint, **vals):
        vals["tracepoint"] = tracepoint
        if tracepoint == StateMachine.TRACE_INPUT:
            self.collapse_loops()  # Retroactively collapse loops so the start of an unrecognized input will be a new entry
            self.input_count += 1
            vals["input_count"] = self.input_count
            self.transitions.append(vals)
        else:
            self.transitions[-1].update(vals)


    def collapse_loops(self):
        if len(self.transitions) < 2:
            return  # No loop to collapse
        previous = self.transitions[-2]
        latest = self.transitions[-1]
        if previous["state"] == latest["state"]:
            latest["loop_count"] = previous.get("loop_count", 0) + 1
            self.transitions.pop()
            self.transitions[-1].update(latest)


    def throw(self, i):
        """Raises a `ValueError` for an unrecognized input to a `StateMachine` with a trace of that machine's recent significant transitions."""
        trace_lines = "\n".join(self.format_trace())
        s = self.transitions[-1].get("state", "State missing")
        i = self.transitions[-1].get("input", "Input missing")
        c = self.transitions[-1].get("input_count", "Count missing")
        msg = f"Unrecognized input\nStateMachine Traceback (most recent transition last):\n{trace_lines}\nValueError: '{s}' did not recognize {c}: '{i}'"
        raise ValueError(msg)


    def format_transition(self, t):
        tp = t.get("tracepoint", "Tracepoint missing")
        if tp == StateMachine.TRACE_NEW_STATE:
            # Most transitions will be "complete"
            looped = "    ({loop_count} loops in '{state}' elided)\n".format_map(t) if "loop_count" in t else ""
            return looped + "{input_count}: {state}('{input}') > {label}: {result} -- {response} --> {new_state}".format_map(t)
        if tp == StateMachine.TRACE_UNRECOGNIZED:
            # Custom unrecognized format
            return "{input_count}: {state}('{input}') > No match".format_map(t)
        return f"PARTIAL: {str(t)}"  # If transition somehow did not complete but also is not unrecognized, simply dump it for debugging


    def format_trace(self):
        return [ self.format_transition(t) for t in self.transitions ]


class ContextTracer(object):
    """
    Collects the context (e.g. current state, rule label, test result, destination, etc) of a StateMachine evaluating an input.
    """
    def __init__(self):
        self.context = {}
        self.input_count = 0


    def __call__(self, tracepoint, **vals):
        if tracepoint == StateMachine.TRACE_INPUT:
            self.input_count += 1
            vals["input_count"] = self.input_count
            self.context = vals
        else:
            self.context.update(vals)


    def __getattr__(self, attr):
        if attr not in self.context:
            raise AttributeError(f"context currently has no attribute '{attr}'")
        return self.context[attr]


def MultiTracer(*tracers):
    "Combines multiple tracers"
    def mt(tp, **vals):
        for t in tracers:
            t(tp, **vals)
    return mt
#####


###  Tests  ###
class in_test(object):
    "Callable to test if input is in a collection and format a nice __str__"
    def __init__(self, in_list):
        self.in_list = in_list

    def __call__(self, i):
        return i in self.in_list

    def __str__(self):
        return f"i in {self.in_list}"
#####
