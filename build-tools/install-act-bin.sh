#! /bin/bash

[[ ! -f "galaxy.yml" ]] && echo "Please start this $0 in project root" && exit -1

ACT_VERSION_EXPECTED=$1
[[ -z $ACT_VERSION_EXPECTED ]] && echo -e "Please specify expected version\n usage: $0 <ACT_VERSION_EXPECTED>" && exit -1

ACT_VERSION_ACTUAL=$(.tmp/bin/act --version || echo 'NOT-INSTALLED')
#ACT_VERSION_EXPECTED="0.2.20"
echo "ACT version change: $ACT_VERSION_ACTUAL --> $ACT_VERSION_EXPECTED"

[[ "$ACT_VERSION_ACTUAL" =~ "$ACT_VERSION_EXPECTED" ]] && echo "act already install: $ACT_VERSION_ACTUAL" && exit 0 ;

echo "Installing act $ACT_VERSION_EXPECTED"
mkdir -p .tmp/act-release
mkdir -p .tmp/bin
rm -rf .tmp/act-release/*
cd .tmp/act-release
curl -SL https://github.com/nektos/act/releases/download/v$ACT_VERSION_EXPECTED/act_Linux_x86_64.tar.gz -o "./act_Linux_x86_64.tar.gz"
tar -xzf ./act_Linux_x86_64.tar.gz -C ./
cp -v -f ./act ../bin/act
../bin/act --version