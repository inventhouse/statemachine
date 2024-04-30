# SmallMachine: Copyright © 2021-2024 Benjamin Holt - MIT License

#####


###  State Machine Core  ###

class StateMachine(object):
    """A state machine engine that makes minimal assumptions but includes some nice conveniences and powerful extensibility.
    """

    def __init__(self, rules=None, state=None, tracer=lambda **_: None):
        """Create a state machine instance which can be called with input and returns output from evaluating the rules for the current state.

        The rules dictionary maps each state to a list of rule tuples, each of which includes a label, a test, an action, and a destination; more about rule elements in the __call__ documentation.

        Rules associated with the special ... (Ellipsis) state are implicitly added to all states' rules, and evaluated after explicit rules.

        State is simply the starting state for the machine; it defaults to the first state defined in the rules or None which is not a special value, it is simply a (possibly) valid state.

        Tracer is an optional callable that takes a Tracepoint and its associated values; it is called at critical points in the input processing to follow the internal operation of the machine.  A simple tracer can produce logs that are extremely helpful when debugging, see PrefixTracer for an example.  Tracepoints are distinct constants which can be used by more advanced tracers for selective verbosity, raising errors for unrecognized input or states, and other things.  Tracers can be stacked using MultiTracer.
        """
        # Starting rules and state can be set after init, but really should be set before using the machine
        # rules dict looks like { state: [(label, test, action, new_state), ...], ...}
        self.rules = rules  # if rules is not None else {}
        self.state = state
        self.tracer = tracer
        self._input_count = 0

    def __call__(self, input):
        """Tests an input against the explicit rules for the current state plus the implicit rules from the ... (Ellipsis) state.

        As the rules are evaluated, a context dictionary is built; these keys and values are available to callable rule components as keyword arguments.  Context arguments available when rules are evaluated are: input, input_count, state, and elements of the currently evaluating rule: label, test, action, and dest.

        Each rule consists of a label, test, action, and destination, which work as follows:

        - Label: string used for identifying the "successful" rule when tracing.

        - Test: if callable, it will be called with context arguments, otherwise it will be tested for equality with the input; if the result is truish, the rule succeeds and no other rules are tested and the result is added to the context.

        - Action: when a test succeeds, the action is evaluated and the response is added to the context and returned by this call.  If action callable, it will be called with context arguments, including 'result' from the test above; it is common for the action to have side-effects that are intended to happen when the test is met.  If it is not callable, the action literal will be the response.

        - Destination: finally, if destination is callable it will be called with context arguments, including 'result' and 'response' above, to get the destination state, otherwise the literal value will be the destination.  If the destination state is '...', the machine will remain in the same state (self-transition or "loop".)  Callable destinations can implement state push/pop for recursion, state exit/enter actions, non-deterministic state changes, and other interesting things.
        """
        try:
            self._input_count += 1
            rule_list = self.rules[self.state] + self.rules.get(..., [])
            for l,t,a,d in rule_list:
                result = t(**self.context) if callable(t) else t == input
                if result:
                    response = a(**self.context) if callable(a) else a
                    dest = d(**self.context) if callable(d) else d
                    self.tracer()
                    if dest is not ...:
                        self.state = dest
                    return response
            else:
                return None
        except Exception as e:
            #     note = f"StateMachine Context:\n    {format_transition(**self.context)}"
            #     e.add_note(note)
            raise
#####


###  Tracing  ###
# def PrefixTracer(prefix="T>", printer=print):
#     """Prints tracepoints with a distinctive prefix and, optionally, to a separate destination than other output"""
#     def t(tp, **vals):
#         msg = f"{prefix} {tp.value.format(**vals)}" if prefix else tp.value.format(**vals)
#         printer(msg)
#     return t
#####
