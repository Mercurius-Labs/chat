#! /usr/bin/bash

cd $(dirname $0)
pushd ../../releases/tmp/ > /dev/null
    ./init-db -add_root admin:admin
popd > /dev/null