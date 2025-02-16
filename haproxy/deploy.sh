#!/bin/sh

REPO="/root/hbox-k3s-cluster"
SOURCE="haproxy/haproxy.cfg"
TARGET="/etc/haproxy/haproxy.cfg"
DEPLOY_COMMAND="systemctl restart haproxy"

cd $REPO
git fetch origin
if git status | grep -q behind; then
  git merge origin/main
  cp $SOURCE $TARGET
  $( $DEPLOY_COMMAND )
fi
