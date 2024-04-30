# SmallMachine: Copyright © 2021-2024 Benjamin Holt - MIT License

#####


###  State Machine Core  ###
class StateMachine(object):
    """A state machine engine that makes minimal assumptions but includes some nice conveniences and powerful extensibility.
    """

    def __init__(self, rules, state, tracer=lambda fmt, **_: None):
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
        self._input_count = 0

    def __call__(self, input):
        """Tests an input against the explicit rules for the current state plus the implicit rules from the ... (Ellipsis) state.

        As the rules are evaluated, a context dictionary is built; these keys and values are available to callable rule components as keyword arguments.  Context arguments available when rules are evaluated are: machine, state, input_count, input, and elements of the currently evaluating rule: label, test, action, and dest.

        Each rule consists of a label, test, action, and destination, which work as follows:

        - Label: usually a string, used for identifying the "successful" rule when tracing.

        - Test: called with context arguments; if the result is truish, the rule succeeds, no other rules are tested.

        - Action: when a test succeeds, the action is called with context arguments, including 'result' from the test above; the action's response will be included in the context arguments for the tracer and returned by this call.

        - Destination: finally, the machine will tranition to the destination state unless the destination is ... (Elipsis).
        """
        try:
            self._input_count += 1
            rule_list = self.rules[self.state] + self.rules.get(..., [])
            for l,t,a,d in rule_list:
                ctx = {
                    "machine": self, "state": self.state, 
                    "input_count": self._input_count, "input": input,
                    "label": l, "test": t, "action": a, "dest": d,
                }
                result = t(**ctx)
                if result:
                    response = a(result=result, **ctx)
                    self.tracer(
                        "{input_count}: {state}('{input}') > {label}: {result} -- {response} --> {dest}",
                        result=result, response=response, **ctx,
                    )
                    if d is not ...:
                        self.state = d
                    return response
            else:
                raise ValueError(f"Unrecognized input '{input}'")
        except Exception as e:
            note = f"StateMachine processing  {self._input_count}: {self.state}('{input}')"
            e.add_note(note)
            raise
#####


###  Tracing  ###
def Debug(prefix="T>", printer=print):
    """Prints tracepoint with a distinctive prefix and, optionally, to a separate destination than other output"""
    def t(fmt, **vals):
        msg = f"{prefix} {fmt.format(**vals)}" if prefix else fmt.format(**vals)
        printer(msg)
    return t
#####
