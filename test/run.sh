#!/bin/bash

# This is a simple test script which creates a gearman server, curler worker,
# and basic web service and creates a few jobs. There must be a better way to
# test this stuff...

GEARMAND_PORT=4731
GEARMAN_QUEUE=curler_test
WEBSERVER_PORT=8047

function clean_up {
  # kill services
  echo -e "\n"
  kill $CURLER_PID
  kill $WEBSERVER_PID
  kill $GEARMAND_PID
  exit
}

trap clean_up SIGHUP SIGINT SIGTERM SIGKILL

# start gearmand
echo "Running gearmand on port $GEARMAND_PORT"
gearmand --port $GEARMAND_PORT &
GEARMAND_PID=$!

# start webserver
echo "Running webserver on port $WEBSERVER_PORT"
python webserver.py $WEBSERVER_PORT &
WEBSERVER_PID=$!

# start curler
echo "Running curler"
cd ..
twistd -n curler \
  --base-urls=http://localhost:$WEBSERVER_PORT \
  --job-queue=$GEARMAN_QUEUE \
  --gearmand-server=localhost:$GEARMAND_PORT &
CURLER_PID=$!

# let services fully start
sleep 1

echo "Running jobs..."
echo -e "\n********** Should get 200 - OK **********"
gearman \
  -p $GEARMAND_PORT \
  -f $GEARMAN_QUEUE '{"method": "success", "data": {}, "headers": {"X-TEST-HEADER": "(yey)"}}'

echo -e "\n\n********** Should get 500 - FAIL **********"
gearman \
  -p $GEARMAND_PORT \
  -f $GEARMAN_QUEUE '{"method": "fail", "data": {}}'

clean_up