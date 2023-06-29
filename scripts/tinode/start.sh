#! /usr/bin/bash

cd $(dirname $0)
pushd ../../releases/tmp/ > /dev/null
    ./tinode -log_flags=date,time,shortfile
popd