#!/bin/bash

rf=${1-results.log}

# Displays the module names present in results.log
grep -E "in module" $rf |
    sed -E "s/.*in module '([^']*)'.*/\1/" |
    sort -u
