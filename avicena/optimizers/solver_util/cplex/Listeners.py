from docplex.mp.progress import ProgressListener, ProgressData


class TimeListener(ProgressListener):
    """
    Sample CPLEX Listener found on IBM DoCPLEX Forums. This listener logs and tracks MIP Gap and the time passed
    in attempt to solve the problem. It aborts the solve if a certain amount of time has passed.
    """

    def __init__(self, time: int):
        """
        Initalize Listener
        :param time: time in seconds until the solve attempt will end
        """
        ProgressListener.__init__(self)
        self._time = time

    def notify_progress(self, data: ProgressData) -> None:
        """
        A Callback used by the CPLEX solver to update the listener on the progress so far on the solution.
        :param data: ProgressData struct with details about the solution's progress
        """
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
    Sample CPLEX Listener found on IBM DoCPLEX Forums. This listener logs and tracks MIP Gap and the time passed
    in attempt to solve the problem. It aborts the solve if a certain MIP gap is reached or a certain amount of time has
    passed.
    """

    def __init__(self, time: int, gap: float) -> None:
        """
        Initialize Listener
        :param time: time in seconds until the solve attempt will end
        :param gap: target MIP gap
        """
        ProgressListener.__init__(self)
        self._time = time
        self._gap = gap

    def notify_progress(self, data: ProgressData) -> None:
        """
         A Callback used by the CPLEX solver to update the listener on the progress so far on the solution.
         :param data: ProgressData struct with details about the solution's progress
         """
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
