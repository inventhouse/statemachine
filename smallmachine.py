# SmallMachine: Copyright © 2021-2024 Benjamin Holt - MIT License

from collections import deque
#####


###  State Machine Core  ###
class StateMachine(object):
    """A state machine engine that makes minimal assumptions but includes a few nice conveniences and powerful extensibility.
    """

    def __init__(self, rules, state, tracer=False, history=10):
        """Create a state machine instance which can be called with input and returns output from evaluating the rules for the current state.

        The rules dictionary maps each state to a list of rule tuples, each of which includes a label, a test, an action, and a destination; more about rule elements in the __call__ documentation.

        Rules associated with the special ... (Ellipsis) state are implicitly added to all states' rules, and evaluated after explicit rules.

        State is simply the starting state for the machine.

        Tracer is an optional callable that takes a format and context arguments; it is called after a successful rule is evaluated, right before the machine transitions.  Debug() is a simple and effective tracer.
        """
        # rules dict looks like { state: [(label, test, action, new_state), ...], ...}
        self.rules = rules
        self.state = state
        self.tracer = tracer
        self.history = deque(maxlen=history)
        self._input_count = 0

    def __call__(self, input):
        """Tests an input against the explicit rules for the current state plus the implicit rules from the ... (Ellipsis) state.

        As the rules are evaluated, a context dictionary is built; these keys and values are available to callable rule components as keyword arguments.  Context arguments available when rules are evaluated are: machine, state, input_count, input, and elements of the currently evaluating rule: label, test, action, and dest.

        Each rule consists of a label, test, action, and destination, which work as follows:

        - Label: usually a string, used for identifying the "successful" rule when tracing.

        - Test: called with context arguments; if the result is truish, the rule succeeds, no other rules are tested.

        - Action: when a test succeeds, the action is called with context arguments, including 'result' from the test above; the action's response will be included in the context arguments for the tracer and returned by this call.

        - Destination: finally, the machine will transition to the destination state unless the destination is ... (Ellipsis).

        At the end of a successful transition, the internal and any custom tracer is called with a transition format and context arguments.
        """
        try:
            self._input_count += 1
            rule_list = self.rules.get(self.state, []) + self.rules.get(..., [])
            for l,t,a,d in rule_list:
                context = {
                    "machine": self, "state": self.state, 
                    "input_count": self._input_count, "input": input,
                    "label": l, "test": t, "action": a, "dest": d,
                }
                result = t(**context)
                if result:
                    response = a(result=result, **context)
                    if d is not ...:
                        self.state = d
                    self._trace(result=result, response=response, new_state=self.state, **context,)
                    if self.state not in self.rules:
                        raise RuntimeError(f"State '{self.state}' is not in the ruleset")
                    return response
            else:
                raise ValueError(f"State '{self.state}' did not recognize input {self._input_count}: '{input}'")
        except Exception as e:
            trace_lines = "\n  ".join(self.format_trace())
            e.add_note(f"StateMachine Traceback (most recent last):\n  {trace_lines}\n{type(e).__name__}: {e}")
            raise

    _transition_fmt = "{input_count}: {state}('{input}') > {label}: {result} -- {response} --> {new_state}"
    def _trace(self, **context):
        if self.tracer:
            if callable(self.tracer):
                self.tracer(self._transition_fmt, **context)
            else:
                prefix = self.tracer if self.tracer is not True else "T>"
                print(f"{prefix} {self._transition_fmt.format(**context)}")
        self.history.append(context)

    def format_trace(self):
        """Returns a list of trace lines from the history of the machine's transitions."""
        return [self._transition_fmt.format(**context) for context in self.history]
#####


###  Tracing  ###
def PrefixTracer(prefix="T>", printer=print):
    """Prints tracepoint with a distinctive prefix and, optionally, to a separate destination than other output"""
    def t(fmt, **vals):
        msg = f"{prefix} {fmt.format(**vals)}" if prefix else fmt.format(**vals)
        printer(msg)
    return t
#####
