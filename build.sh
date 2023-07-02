#!/bin/bash

# This script builds and archives binaries and supporting files for mac, linux, and windows.
# If directory ./server/static exists, it's asumed to contain TinodeWeb and then it's also
# copied and archived.

# Supported OSs: mac (darwin), windows, linux.
goplat=( linux )

# CPUs architectures: amd64 and arm64. The same order as OSs.
goarc=( amd64 )

# Number of platform+architectures.
buildCount=${#goplat[@]}

# Supported database tags
# dbadapters=( mysql mongodb rethinkdb postgres )
# dbtags=( ${dbadapters[@]} alldbs )
dbtags=( postgres )

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

GOSRC=..

pushd ${GOSRC}/chat > /dev/null

# Tar on Mac is inflexible about directories. Let's just copy release files to
# one directory.
rm -fR ./releases/
mkdir -p ./releases/${version}/templ

# Copy templates and database initialization files
cp ./server/tinode.conf ./releases/${version}
cp ./server/templ/*.templ ./releases/${version}/templ
cp ./tinode-db/data.json ./releases/${version}
cp ./tinode-db/*.jpg ./releases/${version}
cp ./tinode-db/credentials.sh ./releases/${version}

# Create directories for and copy TinodeWeb files.
if [[ -d ./server/static ]]
then
  mkdir -p ./releases/${version}/static/img
  mkdir ./releases/${version}/static/css
  mkdir ./releases/${version}/static/audio
  mkdir ./releases/${version}/static/src
  mkdir ./releases/${version}/static/umd

  cp ./server/static/img/*.png ./releases/${version}/static/img
  cp ./server/static/img/*.svg ./releases/${version}/static/img
  cp ./server/static/img/*.jpeg ./releases/${version}/static/img
  cp ./server/static/audio/*.m4a ./releases/${version}/static/audio
  cp ./server/static/css/*.css ./releases/${version}/static/css
  cp ./server/static/index.html ./releases/${version}/static
  cp ./server/static/index-dev.html ./releases/${version}/static
  cp ./server/static/version.js ./releases/${version}/static
  cp ./server/static/umd/*.js ./releases/${version}/static/umd
  cp ./server/static/manifest.json ./releases/${version}/static
  cp ./server/static/service-worker.js ./releases/${version}/static
  # Create empty FCM client-side config.
  # echo 'const FIREBASE_INIT = {};' > ./releases/${version}/static/firebase-init.js
else
  echo "TinodeWeb not found, skipping"
  rm -rf ./server/static_tmp
  mkdir -p ./server/static_tmp
  pushd ./server/static_tmp > /dev/null
    wget https://github.com/tinode/webapp/archive/master.zip
    unzip master.zip
    cp -a webapp-master/* ./
    rm master.zip

    wget https://github.com/tinode/tinode-js/archive/master.zip
    unzip master.zip
    cp -a tinode-js-master/* ./
    rm master.zip
  popd
fi

for (( i=0; i<${buildCount}; i++ ));
do
  plat="${goplat[$i]}"
  arc="${goarc[$i]}"

  # Use .exe file extension for binaries on Windows.
  ext=""
  if [ "$plat" = "windows" ]; then
    ext=".exe"
  fi

  # Remove possibly existing keygen from previous build.
  rm -f ./releases/${version}/keygen
  rm -f ./releases/${version}/keygen.exe

  # Keygen is database-independent
  env GOOS="${plat}" GOARCH="${arc}" go build -ldflags "-s -w" -o ./releases/${version}/keygen${ext} ./keygen > /dev/null

  for dbtag in "${dbtags[@]}"
  do
    echo "Building ${dbtag}-${plat}/${arc}..."

    # Remove possibly existing binaries from previous build.
    rm -f ./releases/${version}/tinode
    rm -f ./releases/${version}/tinode.exe
    rm -f ./releases/${version}/init-db
    rm -f ./releases/${version}/init-db.exe

    # Build tinode server and database initializer for RethinkDb and MySQL.
    # For 'alldbs' tag, we compile in all available DB adapters.
    if [ "$dbtag" = "alldbs" ]; then
      buildtag="${dbadapters[@]}"
    else
      buildtag=$dbtag
    fi

    env GOOS="${plat}" GOARCH="${arc}" go build \
      -ldflags "-s -w -X main.buildstamp=`git describe --tags`" -tags "${buildtag}" \
      -o ./releases/${version}/tinode${ext} ./server > /dev/null
    env GOOS="${plat}" GOARCH="${arc}" go build \
      -ldflags "-s -w" -tags "${buildtag}" -o ./releases/${version}/init-db${ext} ./tinode-db > /dev/null


  done
done

popd > /dev/null
