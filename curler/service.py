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


class CurlerService(Service):

    def __init__(self, base_urls, gearmand_server, job_queue, num_workers,
                 verbose=False):
        self.base_urls = base_urls
        self.gearmand_server = gearmand_server
        self.job_queue = job_queue
        self.num_workers = num_workers
        self.verbose = verbose

    @defer.inlineCallbacks
    def startService(self):
        Service.startService(self)
        log.msg('Service starting. gearmand=%r, job queue=%s, base urls=%r'
                % (self.gearmand_server, self.job_queue, self.base_urls))
        self.log_verbose('Verbose logging is enabled.')

        host, port = self.gearmand_server.split(':')
        c = protocol.ClientCreator(reactor, client.GearmanProtocol)
        try:
            proto = yield c.connectTCP(host, int(port))
            self.start_work(proto)
        except Exception, e:
            log.msg("ERROR: Unable to connect & start workers: %s" % e)
            reactor.stop()

    def start_work(self, proto):
        log.msg('Connected to Gearman: %r' % proto)
        worker = client.GearmanWorker(proto)
        worker.registerFunction(self.job_queue, self.handle_job)

        log.msg('Firing up %d workers...' % self.num_workers)
        coop = task.Cooperator()
        for i in range(self.num_workers):
            reactor.callLater(0.1 * i, lambda: coop.coiterate(worker.doJobs()))

    def stopService(self):
        Service.stopService(self)
        log.msg('Service stopping')

    @defer.inlineCallbacks
    def handle_job(self, job):
        time_start = time()
        try:
            log.msg('Got job: %s' % job.handle)
            self.log_verbose('data=%r' % job.data)
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

    def log_verbose(self, message):
        if self.verbose:
            log.msg("VERBOSE: %s" % message)

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
            self.log_verbose('POSTing to %s, data=%r' % (url, data))
            postdata = urllib.urlencode({"data": data})
            headers = {'Content-Type': 'application/x-www-form-urlencoded'}
            try:
                # despite our name, we're not actually using curl :)
                response = yield getPage(url, method='POST', postdata=postdata,
                                         headers=headers)
                status = 200
            except Error, e:
                status = int(e.status)
                response = e.response
            self.log_verbose('POST complete: status=%d, response=%r'
                             % (status, response))
            defer.returnValue({'url': url,
                               'status': status,
                               'response': response})
        except Exception, e:
            defer.returnValue({"error": "POST failed: %r - %s" % (e, e)})
