import sys
from curler.curler import CurlerService
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
        ["job-queue", "q", "curl",
            "Job queue to get jobs from."],
        ["job-servers", "j", "localhost:4730",
          "Gearman job servers. Separate with commas."]]

    longdesc = 'curler is a Gearman worker service which does work by curling \
        a web service. \nPlease see http://github.com/powdahound/curler to \
        report issues or get help.'


class CurlerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "curler"
    description = "A Gearman worker that cURLs to do work."
    options = Options

    def makeService(self, options):
        if not options['curl-paths'] or not options['job-servers'] \
            or not options['job-queue']:
            print options
            sys.exit(1)

        curl_paths = options['curl-paths'].split(',')
        job_servers = options['job-servers'].split(',')
        job_queue = options['job-queue']
        verbose = bool(options['verbose'])
        return CurlerService(curl_paths, job_servers, job_queue, verbose)


serviceMaker = CurlerServiceMaker()
