#!/bin/bash

NT_NAME=$1

if [[ -z $NT_NAME ]]; then
  echo -e "Please provide a network name.\nusage:\n\t$0 <network name>"
  exit 1
fi

NT_FOUND=$(docker network inspect $NT_NAME --format "{{ .Name }}"  2> /dev/null)
if [[ $NT_FOUND == "$NT_NAME" ]]; then
  echo -e "Network $NT_NAME already exists; skipping creation!"
  exit 0
fi

echo "Creating $NT_NAME"

docker network create -d bridge $NT_NAME
