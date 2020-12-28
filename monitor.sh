#!/bin/bash

rf=${1-results.log}

for str in fail exception success valid invalid; do
    echo $str:
    grep -iE "\b$str" $rf
    if [ $? -ne 0 ]; then
        echo "(None)"
    fi
    echo
done

# also show "success" jobs that are neither valid nor invalid
echo not validated:
grep -i success $rf | grep -v valid
if [ $? -ne 0 ]; then
    echo "(None)"
fi
echo
