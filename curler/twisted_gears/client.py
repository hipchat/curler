"""
Gearman client implementation.
"""

import sys
import struct

from collections import deque

from twisted.internet import defer
from twisted.protocols import stateful
from twisted.python import log

from constants import *

__all__ = ['GearmanProtocol', 'GearmanWorker', 'GearmanClient']

class GearmanProtocol(stateful.StatefulProtocol):
    """Base protocol for handling gearman connections."""

    unsolicited = [ WORK_COMPLETE, WORK_FAIL, NOOP,
                    WORK_DATA, WORK_WARNING, WORK_EXCEPTION ]

    def makeConnection(self, transport):
        self.receivingCommand = 0
        self.deferreds = deque()
        self.unsolicited_handlers = set()
        # curler: moved this to the end so that vars are initialized when
        # connectionMade() gets called
        stateful.StatefulProtocol.makeConnection(self, transport)

    def send_raw(self, cmd, data=''):
        """Send a command with the given data with no response."""

        self.transport.writeSequence([REQ_MAGIC,
                                      struct.pack(">II", cmd, len(data)),
                                      data])

    def send(self, cmd, data=''):
        """Send a command and get a deferred waiting for the response."""
        self.send_raw(cmd, data)
        d = defer.Deferred()
        self.deferreds.append(d)
        return d

    def getInitialState(self):
        return self._headerReceived, HEADER_LEN

    def connectionLost(self, reason):
        for d in list(self.deferreds):
            d.errback(reason)
        self.deferreds.clear()

    def _headerReceived(self, header):
        if header[:4] != RES_MAGIC:
            log.msg("Invalid header magic returned, failing.")
            self.transport.loseConnection()
            return
        cmd, size = struct.unpack(">II", header[4:])

        self.receivingCommand = cmd
        return self._completed, size

    def _completed(self, data):
        if self.receivingCommand in self.unsolicited:
            self._unsolicited(self.receivingCommand, data)
        else:
            d = self.deferreds.popleft()
            d.callback((self.receivingCommand, data))
        self.receivingCommand = 0

        return self._headerReceived, HEADER_LEN

    def _unsolicited(self, cmd, data):
        for cb in self.unsolicited_handlers:
            cb(cmd, data)

    def register_unsolicited(self, cb):
        self.unsolicited_handlers.add(cb)

    def unregister_unsolicited(self, cb):
        self.unsolicited_handlers.discard(cb)

    def echo(self, data="hello"):
        """Send an echo request."""

        return self.send(ECHO_REQ, data)

class _GearmanJob(object):
    """A gearman job."""

    def __init__(self, raw_data):
        self.handle, self.function, self.data = raw_data.split("\0", 2)

    def __repr__(self):
        return "<GearmanJob %s func=%s with %d bytes of data>" % (self.handle,
                                                                  self.function,
                                                                  len(self.data))

class GearmanWorker(object):
    """A gearman worker."""

    def __init__(self, protocol):
        self.protocol = protocol
        self.functions = {}
        self.sleeping = None
        self.protocol.register_unsolicited(self._unsolicited)

    def setId(self, client_id):
        """Set the client ID for monitoring and what-not."""
        self.protocol.send_raw(SET_CLIENT_ID, client_id)

    def registerFunction(self, name, func):
        """Register the ability to perform a function."""

        self.functions[name] = func
        self.protocol.send_raw(CAN_DO, name)

    def _send_job_res(self, cmd, job, data=''):
        self.protocol.send_raw(cmd, job.handle + "\0" + data)

    def _sleep(self):
        if not self.sleeping:
            self.sleeping = defer.Deferred()
            self.protocol.send_raw(PRE_SLEEP)
        return self.sleeping

    def _unsolicited(self, cmd, data):
        assert cmd == NOOP
        if self.sleeping:
            self.sleeping.callback(None)
            self.sleeping = None

    @defer.inlineCallbacks
    def getJob(self):
        """Get the next job."""

        # If we're currently sleeping, attach to the existing sleep.
        if self.sleeping:
            yield self._sleep()

        stuff = yield self.protocol.send(GRAB_JOB)
        while stuff[0] == NO_JOB:
            yield self._sleep()
            stuff = yield self.protocol.send(GRAB_JOB)
        defer.returnValue(_GearmanJob(stuff[1]))

    @defer.inlineCallbacks
    def _finishJob(self, job):
        assert job
        f = self.functions[job.function]
        assert f
        try:
            rv = yield f(job)
            if rv is None:
                rv = ""
            self._send_job_res(WORK_COMPLETE, job, rv)
        except:
            etype, emsg, bt = sys.exc_info()
            self._send_job_res(WORK_EXCEPTION, job, "%s(%s)"
                               % (etype.__name__, emsg))
            self._send_job_res(WORK_FAIL, job)

    def doJob(self):
        """Do a single job"""
        return self.getJob().addCallback(self._finishJob)

    def doJobs(self, keepGoing=lambda: True):
        """Do jobs forever (or until the given function returns False)"""
        while keepGoing():
            yield self.doJob()

class _GearmanJobHandle(object):

    def __init__(self, deferred):
        self._deferred = deferred
        self._work_data = []
        self._work_warning = []

    @property
    def work_data(self):
        return ''.join(self._work_data)

    @property
    def work_warning(self):
        return ''.join(self._work_warning)

class GearmanJobFailed(Exception):
    """Exception thrown when a job fails."""
    pass

class GearmanClient(object):
    """A gearman client.

    Submits jobs and stuff."""

    def __init__(self, protocol):
        self.protocol = protocol
        self.protocol.register_unsolicited(self._unsolicited)
        self.jobs = {}

    def _register(self, job_handle, job):
        self.jobs[job_handle] = job

    def _unsolicited(self, cmd, data):
        if cmd in [ WORK_COMPLETE, WORK_FAIL,
                    WORK_DATA, WORK_WARNING ]:
            pos = data.find("\0")
            if pos == -1:
                handle = data
            else:
                handle = data[:pos]
                data = data[pos+1:]

            j = self.jobs[handle]

            if cmd in [ WORK_COMPLETE, WORK_FAIL]:
                self._jobFinished(cmd, j, handle, data)

    def _jobFinished(self, cmd, job, handle, data):
        # Delete the job if it's finished
        del self.jobs[handle]

        if cmd == WORK_COMPLETE:
            job._deferred.callback(data)
        elif cmd == WORK_FAIL:
            job._deferred.errback(GearmanJobFailed())

    def _submit(self, cmd, function, data, unique_id):

        def _submitted(x, d):
            self._register(x[1], _GearmanJobHandle(d))

        d = self.protocol.send(cmd,
                               function + "\0" + unique_id + "\0" + data)

        rv = defer.Deferred()
        d.addCallback(_submitted, rv)

        return rv

    def submit(self, function, data, unique_id=''):
        """Submit a job with the given function name and data."""
        return self._submit(SUBMIT_JOB, function, data, unique_id)

    def submitHigh(self, function, data, unique_id=''):
        """Submit a high priority job with the given function name and data."""
        return self._submit(SUBMIT_JOB_HIGH, function, data, unique_id)

    def submitLow(self, function, data, unique_id=''):
        """Submit a low priority job with the given function name and data."""
        return self._submit(SUBMIT_JOB_LOW, function, data, unique_id)

    def _submitBg(self, cmd, function, data, unique_id):
        return self.protocol.send(cmd,
                                  function + "\0" + unique_id + "\0" + data)

    def submitBackground(self, function, data, unique_id=''):
        """Submit a job for background execution."""
        return self._submitBg(SUBMIT_JOB_BG, function, data, unique_id)

    def submitBackgroundLow(self, function, data, unique_id=''):
        """Submit a job for background execution at low priority."""
        return self._submitBg(SUBMIT_JOB_LOW_BG, function, data, unique_id)

    def submitBackgroundHigh(self, function, data, unique_id=''):
        """Submit a job for background execution at high priority."""
        return self._submitBg(SUBMIT_JOB_HIGH_BG, function, data, unique_id)
