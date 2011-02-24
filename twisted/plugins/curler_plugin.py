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
        ["base-urls", "u", None,
            "Base paths to curl. Separate with commas."],
        ["job-queue", "q", "curler",
            "Job queue to get jobs from."],
        ["gearmand-server", "g", "localhost:4730",
          "Gearman job server."],
        ["num-workers", "n", 5,
          "Number of workers (max parallel jobs)."]]

    longdesc = 'curler is a Gearman worker service which does work by hitting \
        a web service. \nPlease see http://github.com/powdahound/curler to \
        report issues or get help.'


class CurlerServiceMaker(object):
    implements(IServiceMaker, IPlugin)
    tapname = "curler"
    description = "A Gearman worker that cURLs to do work."
    options = Options

    def makeService(self, options):
        if not options['base-urls'] or not options['gearmand-server'] \
            or not options['job-queue'] or not options['num-workers']:
            print options
            sys.exit(1)

        base_urls = options['base-urls'].split(',')
        gearmand_server = options['gearmand-server']
        job_queue = options['job-queue']
        num_workers = int(options['num-workers'])
        verbose = bool(options['verbose'])
        return CurlerService(base_urls, gearmand_server, job_queue, num_workers,
                             verbose)


serviceMaker = CurlerServiceMaker()
