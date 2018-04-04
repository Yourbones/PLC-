import unittest

from middleware import Middleware, Handler

class AdditionMiddleware1(Middleware):
    def create(self):
        def func(mwa, context):
            try:
                counter = context['counter']
            except:
                counter = 0
            context['counter'] = counter + 1

            return next(mwa)

        return func


class AdditionMiddleware2(AdditionMiddleware1):
    pass


class AdditionMiddleware3(AdditionMiddleware1):
    pass

class StopMiddleware(Middleware):
    def create(self):
        def func(mwa, context):
            pass

        return func

class MultiReadWriteMiddleware(Middleware):
    def create(self):
        def func(mwa, context):
            (a, b, c, counter) = self.read(context, 'a', 'b', 'c', 'counter')

            self.write(context, **{ 'a': a * 2, 'b': b * 2, 'counter': counter * 2})

            return next(mwa)

        return func


class TestBuilderCreator(unittest.TestCase):
    def test_stop(self):
        handler = Handler()
        handler.add(AdditionMiddleware1)
        handler.add(StopMiddleware)
        handler.execute()
        self.assertEqual(handler['counter'], 1)

    def test_add(self):
        handler = Handler()
        handler.add(AdditionMiddleware1)
        handler.execute()
        self.assertEqual(handler['counter'], 1)

    def test_chain(self):
        handler = Handler()
        handler.set([AdditionMiddleware1, AdditionMiddleware2])
        handler.add(AdditionMiddleware3)
        handler.execute()
        self.assertEqual(handler['counter'], 3)

    def test_init(self):
        handler = Handler(counter=1)
        handler.set([AdditionMiddleware1, AdditionMiddleware2])
        handler.add(AdditionMiddleware3)
        handler.execute()
        self.assertEqual(handler['counter'], 4)

    def test_hybrid(self):
        handler = Handler(counter=1)
        handler.set([AdditionMiddleware1, AdditionMiddleware2])
        handler.add(AdditionMiddleware3)
        def inline(wma, context):
            context['myvalue'] = 12
        handler.add(inline)
        handler.execute()
        self.assertEqual(handler['counter'], 4)
        self.assertEqual(handler['myvalue'], 12)

    def test_adhoc(self):
        handler = Handler()
        def inline(wma, context):
            context['myvalue'] = 12
        handler.add(inline)
        handler.execute()
        self.assertEqual(handler['myvalue'], 12)

    def test_kwargs(self):
        handler = Handler(**{'a': 1, 'b': 2})
        def inline(wma, context):
            context['a'] = context['a'] + context['b']
        handler.add(inline)
        handler.execute()
        self.assertEqual(handler['a'], 3)

    def test_multiread(self):
        handler = Handler(**{'a': 10, 'b': 20, 'c': 30})
        handler.add(AdditionMiddleware1)
        handler.add(MultiReadWriteMiddleware)
        handler.add(AdditionMiddleware2)
        handler.execute()

        self.assertEqual(handler['a'], 20)
        self.assertEqual(handler['b'], 40)
        self.assertEqual(handler['c'], 30)
        self.assertEqual(handler['counter'], 3)


if __name__ == '__main__':
    unittest.main()
