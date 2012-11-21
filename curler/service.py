import json
import random
import traceback
import urllib
from twisted_gears import client
from time import time
from twisted.application.service import Service
from twisted.internet import defer, protocol, reactor, task
from twisted.python import log
from twisted.web.client import getPage, HTTPClientFactory
from twisted.web.error import Error

# we don't want to hear about each web request we make
HTTPClientFactory.noisy = False


# By default, verbose logging is disabled. This function is redefined
# when the service starts if verbose logging is enabled.
log.verbose = lambda x: None


class CurlerClient(client.GearmanProtocol):

    def __init__(self, service, server, base_urls, job_queue, num_workers):
        self.service = service
        self.server = server
        self.base_urls = base_urls
        self.job_queue = job_queue
        self.num_workers = num_workers

    def connectionLost(self, reason):
        log.msg('CurlerClient lost connection to %s: %s'
                % (self.server, reason))
        client.GearmanProtocol.connectionLost(self, reason)

    def connectionMade(self):
        log.msg('CurlerClient made connection to %s' % self.server)
        self.start_work()

    def start_work(self):
        worker = client.GearmanWorker(self)
        worker.registerFunction(self.job_queue, self.handle_job)

        log.msg('Firing up %d workers...' % self.num_workers)
        coop = task.Cooperator()
        for i in range(self.num_workers):
            reactor.callLater(0.1 * i, lambda: coop.coiterate(worker.doJobs()))

    @defer.inlineCallbacks
    def handle_job(self, job):
        time_start = time()
        try:
            log.msg('Got job: %s' % job.handle)
            log.verbose('data=%r' % job.data)
            response = yield self._make_request(job.handle, job.data)
        except Exception, e:
            log.msg('ERROR: Unhandled exception: %r' % e)
            # Log full traceback on multiple lines
            for line in traceback.format_exc().split('\n'):
                log.msg(line)
            response = {"error": "Internal curler error. Check the logs."}

        # always include handle in response
        response['job_handle'] = job.handle

        # log error if we're returning one
        if 'error' in response:
            log.msg('ERROR: %s' % response['error'])
            response['job_data'] = job.data

        # format response nicely
        response_json = json.dumps(response, sort_keys=True, indent=2)

        time_taken = int((time() - time_start) * 1000 + 0.5)
        log.msg('Completed job: %s, method=%s, time=%sms, status=%d'
                % (job.handle, response['url'], time_taken,
                   response.get('status')))
        defer.returnValue(response_json)

    @defer.inlineCallbacks
    def _make_request(self, handle, data):
        # make sure job arg is valid json
        try:
            job_data = json.loads(data, encoding='UTF-8')
        except ValueError, e:
            defer.returnValue({"error": "Job data is not valid JSON"})

        # make sure it contains a method
        if 'method' not in job_data:
            defer.returnValue({"error":
                               "Missing \"method\" property in job data"})

        # make sure it contains data
        if 'data' not in job_data:
            defer.returnValue({"error":
                               "Missing \"data\" property in job data"})

        # we'll post the data as JSON, so convert it back
        data = json.dumps(job_data['data'])

        # select random base URL to hit
        path = random.choice(self.base_urls)
        url = str("%s/%s" % (path, job_data['method']))

        try:
            log.verbose('POSTing to %s, data=%r' % (url, data))
            postdata = urllib.urlencode({
                "job_handle": handle,
                "data": data})
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            try:
                # despite our name, we're not actually using curl :)
                response = yield getPage(url, method='POST', postdata=postdata,
                                         headers=headers)
                status = 200
            except Error, e:
                status = int(e.status)
                response = e.response
            log.verbose('POST complete: status=%d, response=%r'
                             % (status, response))
            defer.returnValue({'url': url,
                               'status': status,
                               'response': response})
        except Exception, e:
            defer.returnValue({"error": "POST failed: %r - %s" % (e, e)})


class CurlerClientFactory(protocol.ReconnectingClientFactory):
    noisy = True
    protocol = CurlerClient

    # retry every 5 seconds for up to 10 minutes
    initialDelay = 5
    maxDelay = 5
    maxRetries = 120

    def __init__(self, service, server, base_urls, job_queue, num_workers):
        self.service = service
        self.server = server
        self.base_urls = base_urls
        self.job_queue = job_queue
        self.num_workers = num_workers

    def buildProtocol(self, addr):
        p = self.protocol(self.service, self.server, self.base_urls,
                          self.job_queue, self.num_workers)
        p.factory = self
        return p


class CurlerService(Service):

    def __init__(self, base_urls, gearmand_servers, job_queue, num_workers,
                 verbose=False):
        self.base_urls = base_urls
        self.gearmand_servers = gearmand_servers
        self.job_queue = job_queue
        self.num_workers = num_workers

        # define verbose logging function
        if verbose:
            log.verbose = lambda x: log.msg('VERBOSE: %s' % x)

    @defer.inlineCallbacks
    def startService(self):
        Service.startService(self)
        log.msg('Service starting. servers=%r, job queue=%s, base urls=%r'
                % (self.gearmand_servers, self.job_queue, self.base_urls))
        log.verbose('Verbose logging is enabled')

        for server in self.gearmand_servers:
            host, port = server.split(':')
            f = CurlerClientFactory(self, server, self.base_urls,
                                    self.job_queue, self.num_workers)
            proto = yield reactor.connectTCP(host, int(port), f)

    def stopService(self):
        Service.stopService(self)
        log.msg('Service stopping')
