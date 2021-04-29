# StateMachine: Copyright © 2021 Benjamin Holt - MIT License

# Compile with mpy-cross to reduce size to ~1KB
# Compile with mpy-cross -O3 to reduce size to <850B (at the expense of assertions and line numbers)

class StateMachine:
    """
    Create a state machine instance
    
    The rules dictionary maps each state to a list of rule tuples, each of which includes a label, a test, an action, and a destination; more about rule elements in the call documentation.

    Rules associated with the special None state are implicitly added to all states' rules, to be evaluated after explicit rules.

    State is simply the starting state for the machine.

    Tracer is an optional callable that takes a message and any values to format into it, and is called at critical points in the input processing to produce logs that are extremely helpful when debugging; for example 'lambda msg, *vals: print(msg.format(*vals))'

    The unrecognized handler is an optional callable that takes input that did not match any rule in the current state nor the implicitly added rules from the None state.  By default it returns None; setting this to raise makes the machine more strict which can help debugging: 'def unexpected_input(i): raise ValueError(f"'Input '{i}' did not match, set tracer to debug")'

    Public attributes can be manipulated after init; for example a rule action could set the state machine's tracer to start or stop logging of the machine's operation.
    """
    def __init__(self, rules, state, tracer=lambda m, *v: None, unrecognized=lambda _: None):
        self.rules = rules  # { state: [(label, test, action, state), ...], ...}
        self.state = state
        self.tracer = tracer
        self.unrecognized = unrecognized


    def __call__(self, i):
        """
        Tests an input against the rules for the current state plus the global rules from the None state.

        Each rule consists of a label, test, action, and destination, which work as follows:

        - Label: string used for identifying the "successful" rule when tracing.

        - Test: if callable, it will be called with the input, otherwise it will be tested for equality with the input; if the result is truish, the rule succeeds and no other rules are tested.

        - Action: when a test succeeds, the action is evaluated and the response is returned by this call.  If action callable, it will be called with the input; it is common for the action to have side-effects that are intended to happen when the test is met.  If it is not callable, the action literal will be returned.

        - Destination: finally, if destination is callable it will be called with the current state to get the destination state, otherwise the literal value will be the destination.  If the destination state is None, the machine will remain in the same state (self-transition or "loop".)  Callable destinations can implement state push/pop for recursion, state exit/enter actions, non-deterministic state changes, and other interesting things.
        """
        self.tracer("{}('{}')", self.state, i)
        rule_list = self.rules.get(self.state, []) + self.rules.get(None, [])
        assert rule_list, "Empty rule list, set tracer to debug"
        for l,t,a,d in rule_list:
            result = t(i) if callable(t) else t == i
            if result:
                self.tracer("  {}: {}", l, result)
                response = a(i) if callable(a) else a
                dest = d(self.state) if callable(d) else d
                self.tracer("    {} --> {}", response, dest)
                if dest is not None:
                    assert dest in self.rules, f"Unknown state '{dest}', set tracer to debug"
                    self.state = dest
                return response
        else:
            self.tracer("\t(No match)")
            return self.unrecognized(i)
