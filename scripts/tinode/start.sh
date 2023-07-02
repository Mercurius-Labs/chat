#! /usr/bin/bash

for line in $@; do
  eval "$line"
done

version=${tag#?}

if [ -z "$version" ]; then
  # Get last git tag as release version. Tag looks like 'v.1.2.3', so strip 'v'.
  version=`git describe --tags`
  version=${version#?}
fi

echo "Releasing $version"

cd $(dirname $0)
pushd ../../releases/${version}/ > /dev/null
    ./tinode -log_flags=date,time,shortfile
popd