#!/usr/bin/env bash
set -e

# Replace the instructions for regenerating requirements/*.txt files

function show_help {
    echo "Usage: post-pip-compile.sh file ..."
    echo "Replace the instructions for regenerating the given requirements file(s)."
}

function clean_file {
    FILE_PATH=$1
    TEMP_FILE=${FILE_PATH}.tmp
    sed "s/pip-compile --output-file.*/make upgrade/" ${FILE_PATH} > ${TEMP_FILE}
    mv ${TEMP_FILE} ${FILE_PATH}
}

for i in "$@"; do
    case ${i} in
        -h|--help)
            # help or unknown option
            show_help
            exit 0
            ;;
        *)
            clean_file ${i}
            ;;
    esac
done
