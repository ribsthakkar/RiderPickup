from docplex.mp.progress import ProgressListener


class TimeListener(ProgressListener):
    """
    Sample Listener found on IBM DoCPLEX Forums
    """

    def __init__(self, time):
        ProgressListener.__init__(self)
        self._time = time

    def notify_progress(self, data):
        print('Elapsed time: %.2f' % data.time)
        if data.has_incumbent:
            print('Current incumbent: %f' % data.current_objective)
            print('Current gap: %.2f%%' % (100. * data.mip_gap))
            # If we are solving for longer than the specified time then
            # stop if we reach the predefined alternate MIP gap.
            if data.time > self._time:
                print('ABORTING')
                self.abort()
        elif data.time > self._time:
            self.abort()
        else:
            # print('No incumbent yet')
            pass


class GapListener(ProgressListener):
    """
    Sample Listener found on IBM DoCPLEX Forums
    """

    def __init__(self, time, gap):
        ProgressListener.__init__(self)
        self._time = time
        self._gap = gap

    def notify_progress(self, data):
        print('Elapsed time: %.2f' % data.time)
        if data.has_incumbent:
            print('Current incumbent: %f' % data.current_objective)
            print('Current gap: %.2f%%' % (100. * data.mip_gap))
            # If we are solving for longer than the specified time then
            # stop if we reach the predefined alternate MIP gap.
            if data.time > self._time or data.mip_gap < self._gap:
                print('ABORTING')
                self.abort()
        else:
            # print('No incumbent yet')
            pass
