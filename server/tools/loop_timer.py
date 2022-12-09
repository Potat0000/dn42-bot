# -*- coding: utf-8 -*-

# Modified the code from the link below:
#   https://www.cnblogs.com/kaerxifa/p/11481047.html
#   https://stackoverflow.com/a/13151299

from threading import Timer


class LoopTimer:
    class MyTimer(Timer):
        def __init__(self, interval, function, name="", *args, **kwargs):
            Timer.__init__(self, interval, function, args, kwargs)
            if name:
                self.name = name

        def run(self):
            while True:
                self.finished.wait(self.interval)
                if self.finished.is_set():
                    break
                self.function(*self.args, **self.kwargs)

    def __init__(self, interval, function, name="", *args, **kwargs):
        self._timer = None
        self.interval = interval
        self.function = function
        self.args = args
        self.kwargs = kwargs
        self.name = name
        self._is_running = False

    def start(self, *args, **kwargs):
        if args:
            self.args = args
        if kwargs:
            self.kwargs = kwargs
        if not self._is_running:
            self._timer = self.MyTimer(self.interval, self.function, self.name, *self.args, **self.kwargs)
            self._timer.daemon = True
            self._timer.start()
            self._is_running = True

    def cancel(self):
        if self._is_running:
            self._timer.cancel()
            self._is_running = False

    @property
    def is_running(self):
        return self._is_running
