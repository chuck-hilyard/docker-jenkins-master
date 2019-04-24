#!/usr/bin/env bash

set -e

git clone https://github.com/chuck-hilyard/jenkins-rl-bin.git /var/jenkins_home/jenkins-rl-bin
chown -R jenkins:jenkins /var/jenkins_home/jenkins-rl-bin

exec "$@"
