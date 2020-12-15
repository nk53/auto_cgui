#!/bin/bash

rf=results.log
if [ -n "$1" ]; then
    rf="$1"
fi

for str in fail exception success; do
    echo $str:
    grep -i $str $rf
    echo
done
