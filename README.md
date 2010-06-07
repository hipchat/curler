curler
=======

A [Gearman][gm] worker which cURLs a web service to do its work. Still missing a number of important worker features like failed jobs and parallel jobs. Use it if those aren't important to you yet.

Why?
----
It's good practice to use background jobs for time-intensive tasks in order to keep your service fast. Unfortunately you have to write workers to perform these tasks and that means you'll have more services to monitor, a more segmented codebase, and may need to rewrite a bunch of your app's logic in another language. With curler, you write the code to process your jobs in your web framework and have access to all the libraries, models, and configuration that you're used to.

Example
-------
Let's say we have a photo sharing site written in PHP which lets users export all their data as a zip file for personal backup and data portability. Since we don't want to make the user wait for 60 seconds while we generate the archive we'll just do it in the background and send them an email when it's ready for download.

**Assumptions**

 * We have a `generate_archive` method in a `jobs` controller available at `http://localhost/jobs/generate_archive`
 * We're running a Gearman server and curler worker on localhost:
   * `gearman -vv`
   * `twistd -n curler --curl-paths=http://localhost/jobs --job-queue=curl`

**Flow**

1. When the user starts the flow we'll create a Gearman job containing their user id and the method that will perform the work.

        $job_data = array(
          'method' => 'generate_archive',
          'data' => array('user_id' => 5)
        );
        $gmc = new GearmanClient();
        $gmc->addServer();
        $gmc->addTaskBackground("curl", json_encode($data));

1. curler will pick up the job and hit `http://localhost/jobs/generate_archive` with the POST data `user_id=5`.

1. In the `generate_archive` method of our `jobs` controller we'll grab `$_POST['user_id']`, generate the archive, and send the user an email with a download link.

Usage
-------
curler runs as a [twistd](http://linux.die.net/man/1/twistd) service. Just go to the /curler directory and run:

    $ twistd curler
    $ tail -f twistd.log
    $ kill `cat twistd.pid`

There are a few arguments to curler:

 * `--curl-paths` - Base URLs for cURLing which the `method` is appended to. You can specify multiple URLs by separating them with commas. One will be chosen at random (defaults to 'http://localhost').
 * `--job-queue` - The Gearman job queue to monitor (defaults to 'curl').
 * `--job-servers` - Gearman job servers to get jobs from. Separate multiple with commas (defaults to 'localhost:4730', gearmand's default).
 * `--verbose` - Enables verbose logging (includes full request/response data)

Dependencies
-------------
 * [Twisted](http://twistedmatrix.com/trac/)
 * [python-gearman](http://github.com/samuel/python-gearman)
 * [pycurl](http://pycurl.sourceforge.net/)
 * [simplejson](http://code.google.com/p/simplejson/)

TODO
----
 * Test script
 * Install script
 * Use urllib instead of pycurl so dependency can be removed
 * Multiple requests in parallel
 * Use [twisted-gears](http://github.com/dustin/twisted-gears) instead of [python-gearman](http://github.com/samuel/python-gearman)
 * Handle failures
 
[gm]: http://gearman.org
[gm-why]: http://highscalability.com/product-gearman-open-source-message-queuing-system
