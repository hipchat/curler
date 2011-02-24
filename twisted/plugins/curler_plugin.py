import sys
from curler.service import CurlerService
from twisted.application.service import IServiceMaker
from twisted.plugin import IPlugin
from twisted.python import usage
from zope.interface import implements


class Options(usage.Options):
    optFlags = [
        ["verbose", "v", "Verbose logging"]]

    optParameters = [
        ["curl-paths", "c", None,
            "Base path to curl. Separate with commas."],
        ["job-queue", "q", "curler",
            "Job queue to get jobs from."],
        ["job-server", "j", "localhost:4730",
          "Gearman job server."],
        ["num-workers", "n", 5,
          "Number of workers (max parallel jobs)."]]

    longdesc = 'curler is a Gearman worker service which does work by curling \
        a web service. \nPlease see http://github.com/powdahound/curler to \
        report issues or get help.'


class CurlerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "curler"
    description = "A Gearman worker that cURLs to do work."
    options = Options

    def makeService(self, options):
        if not options['curl-paths'] or not options['job-server'] \
            or not options['job-queue'] or not options['num-workers']:
            print options
            sys.exit(1)

        curl_paths = options['curl-paths'].split(',')
        job_server = options['job-server']
        job_queue = options['job-queue']
        num_workers = int(options['num-workers'])
        verbose = bool(options['verbose'])
        return CurlerService(curl_paths, job_server, job_queue, num_workers,
                             verbose)


serviceMaker = CurlerServiceMaker()
