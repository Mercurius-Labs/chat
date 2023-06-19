#! /usr/bin/bash

cd $(dirname $0)
pushd ../../releases/tmp/ > /dev/null
    ./tinode
popd