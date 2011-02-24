curler
=======

A [Gearman][gm] worker which hits a web service to do its work. Why? Because you already have a bunch of solid code in your web framework and don't want to port it to a standalone worker service.

Basic flow:

1. User #10 on your service submits a form requesting some time-intensive task.
1. You insert a job into the `curler` Gearman queue with the data `{"method": "do_thing", "data": 10}`
1. curler receives the job and POSTs to `http://localhost/jobs/do_thing` with `data=10`.
1. You pull `10` from `post['data']` and do the thing.

Installation & Usage
--------------------
curler runs as a [twistd](http://linux.die.net/man/1/twistd) service. To install & run:

    $ git clone http://github.com/powdahound/curler.git
    $ cd curler/
    $ sudo python setup.py install
    $ twistd --nodaemon curler --base-urls=http://localhost/jobs

There are a few arguments to curler:

 * `--base-urls` - Base URLs which the `method` property is appended to. You can specify multiple URLs by separating them with commas and one will be chosen at random.
 * `--job-queue` - The Gearman job queue to monitor (defaults to 'curler').
 * `--gearmand-server` - Gearman job servers to get jobs from (defaults to 'localhost:4730').
 * `--num-workers` - Number of workers to run (# of jobs you can process in parallel). Uses nonblocking Twisted APIs instead of spawning extra processes or threads. Defaults to 5.
 * `--verbose` - Enables verbose logging (includes full request/response data).

Run `twistd --help` to see how to run as a daemon.

Job data
-------

Jobs inserted into the curler queue must contain two properties:

 * `method` - Relative path of the URL to hit.
 * `data` - Arbitrary data string. POSTed as the `data` property. Use JSON if you need structure.

Dependencies
-------------
 * Python 2.6+
 * [Twisted](http://twistedmatrix.com/trac/)

[gm]: http://gearman.org
