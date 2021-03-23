#!/bin/bash

# awk ouput -> default via 172.17.0.1 dev eth0
HOST_ADDR=$(docker run alpine /bin/sh -c "ip route|awk '/default/ { print $3 }' | sed 's/.*via \(.*\)* dev.*/\1/';" 2> /dev/null || echo "")


if [[ -z $HOST_ADDR ]]; then
  exit 0
fi

APT_PROXY="http://$HOST_ADDR:3142"

if curl --head --silent $APT_PROXY 2> /dev/null 1> /dev/null;
 then
  echo "$APT_PROXY"
 else
  echo ""
fi
exit 0