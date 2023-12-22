#!/bin/bash
set -e

if [ "$EXTRAS" = "gradio" ]; then
    exec iris start-gradio
    elif [ "$EXTRAS" = "web_sat" ]; then
    exec iris start-websat
else
    echo "No extras specified, showing help. To execute a command, use 'docker run iris <command>'"
    exec iris -h
fi
