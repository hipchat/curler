import logging
import pycurl
import random
import simplejson
import StringIO
import urllib
from gearman.worker import GearmanWorker
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
        worker.register_function(self.job_queue, self.do_curl)
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

    def do_curl(self, job):
        self.log_verbose('Got job: handle=%s, arg=%r' % (job.handle, job.arg))

        # make sure job arg is valid json
        try:
            job_data = simplejson.loads(job.arg)
        except ValueError, e:
            log.msg('ERROR: Job data not valid JSON: %r' % e)
            return False

        # make sure it contains a method
        if 'method' not in job_data:
            log.msg("ERROR: Missing 'method' in job data: %r" % job_data)
            return False

        # make sure it contains data
        if 'data' not in job_data:
            log.msg("ERROR: Missing 'data' in job data: %r" % job_data)
            return False

        method = job_data['method']
        data = job_data['data']

        for key, value in data.items():
            # encode any unicode as utf-8 before urlencoding
            if isinstance(value, unicode):
                data[key] = value.encode('utf-8')
            # convert True/False (true/false in json) to 1/0
            if isinstance(value, bool):
                data[key] = int(value)
            # convert None (null in json) to empty string
            if value is None:
                data[key] = ''

        # perform the curl
        path = random.choice(self.curl_paths)
        url = "%s/%s" % (path, method)
        self.log_verbose('cURLing: url=%s, data=%r' % (url, data))
        b = StringIO.StringIO()
        c = pycurl.Curl()
        c.setopt(c.URL, str(url))
        c.setopt(c.POSTFIELDS, urllib.urlencode(data))
        c.setopt(pycurl.FOLLOWLOCATION, 1)
        c.setopt(pycurl.WRITEFUNCTION, b.write)
        try:
            c.perform()
            code = int(c.getinfo(pycurl.HTTP_CODE))
            time = int(c.getinfo(pycurl.TOTAL_TIME))
            response = b.getvalue()
            c.close()

            # check response code for success
            log.msg('Job complete: code=%d, url=%s, time=%0.2fs'
                    % (code, url, time))
            self.log_verbose('response=%r' % response)

            reply = {'code': code,
                     'response': response}
            return simplejson.dumps(reply)
        except pycurl.error, e:
            log.msg('ERROR: cURL failed: %r - %r' % (e[0], e[1]))
            return False

    def log_verbose(self, message):
        if self.verbose:
            log.msg("VERBOSE: %s" % message)
