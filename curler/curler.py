import json
import random
import traceback
import urllib
import urllib2
from gearman.worker import GearmanWorker
from time import time
from twisted.application.service import Service
from twisted.internet import reactor
from twisted.python import log


class CurlerService(Service):

    def __init__(self, curl_paths, job_servers, job_queue, verbose=False):
        self.curl_paths = curl_paths
        self.job_servers = job_servers
        self.job_queue = job_queue
        self.verbose = verbose

    def startService(self):
        Service.startService(self)
        log.msg('Service starting. servers=%r, queue=%s, curl paths=%r'
                % (self.job_servers, self.job_queue, self.curl_paths))
        self.log_verbose('Verbose logging is enabled.')
        worker = GearmanWorker(self.job_servers)
        worker.register_task(self.job_queue, self.handle_job)
        try:
            worker.work()
        except KeyboardInterrupt, SystemExit:
            # The worker.work() is a blocking call (yeah, we're abusing
            # Twisted) so we want to capture interrupts and shut down the
            # service properly so we don't crash the whole Twisted process.
            log.msg('Worker interrupted.')
            reactor.sigInt()

    def stopService(self):
        Service.stopService(self)
        log.msg('Service stopping')

    def handle_job(self, worker, job):
        time_start = time()
        try:
            log.msg('Got job: %s' % job.handle)
            self.log_verbose('worker=%r, job=%r' % (worker, job))
            response = self._do_curl(worker, job)
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

        response_json = json.dumps(response, sort_keys=True, indent=2)

        time_taken = int((time() - time_start) * 1000 + 0.5)
        log.msg('Completed job: %s, time=%sms'
                % (job.handle, time_taken))
        return response_json

    def log_verbose(self, message):
        if self.verbose:
            log.msg("VERBOSE: %s" % message)

    def _do_curl(self, worker, job):
        # make sure job arg is valid json
        try:
            job_data = json.loads(job.data, encoding='UTF-8')
        except ValueError, e:
            return {"error": "Job data is not valid JSON"}

        # make sure it contains a method
        if 'method' not in job_data:
            return {"error": "Missing \"method\" property in job data"}

        # make sure it contains data
        if 'data' not in job_data:
            return {"error": "Missing \"data\" property in job data"}

        # we'll post the data as JSON, so convert it back
        data = json.dumps(job_data['data'])

        # select random curl path to hit
        path = random.choice(self.curl_paths)
        url = "%s/%s" % (path, job_data['method'])

        try:
            # oh no, we're not actually using curl :)
            self.log_verbose('POSTing to %s, data=%r' % (url, data))
            post_data = urllib.urlencode({"data": data})
            r = urllib2.urlopen(url, post_data)
            code = r.getcode()
            response = r.read()
            self.log_verbose('urlopen complete: code=%d, response=%r'
                             % (code, response))
            return {'response_code': code, 'response': response}
        except Exception, e:
            return {"error": "urlopen failed: %r" % e}
