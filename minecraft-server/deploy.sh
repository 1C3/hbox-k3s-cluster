#!/bin/sh

REPO="/root/hbox-k3s-cluster"
FOLDER="minecraft-server"
DEPLOY_COMMAND="podman build -t minecraft-server:local ."

cd $REPO
git fetch origin
if git status | grep -q behind; then
  git merge origin/main
  cd $FOLDER
  $( $DEPLOY_COMMAND )
fi
