import types

class Middleware():
    def __init__(self, action=None):
        self._action = action

    def read(self, context, *args):
        return [context[_] for _ in args]

    def write(self, context, **kwargs):
        context.update(kwargs)

    def execute(self, mwa, context):
        if self._action is not None:
            self._action(mwa, context)
        else:
            self.process(mwa, context)


class Handler():
    def __init__(self, **kwargs):
        self.middleware_array = []
        self._context = kwargs or {}

    def __getitem__(self, name):
        try:
            return self._context[name]
        except:
            return None

    def __setitem__(self, name, value):
        self._context[name] = value

    def set(self, middleware_array):
        for middleware in middleware_array:
            self.add(middleware)

    def add(self, middleware):
        if isinstance(middleware, types.FunctionType):
            self.middleware_array.append(middleware)
        else:
            self.middleware_array.append(middleware().create())

    def execute(self):
        iteration = iter(self.middleware_array)
        try:
            wm = next(iteration)
            while wm is not None:
                wm = wm(iteration, self._context)
        except StopIteration:
            pass
