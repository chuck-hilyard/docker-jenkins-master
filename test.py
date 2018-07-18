#!/usr/bin/env python3
import http.client
import requests
import subprocess
import time


# add github repos to this jenkins server
f = open('repos.txt', 'r')
repos = []
for repo in f:
  print("repo is a ", type(repo))
  REPO_NAME = repo.split("~",1)[0]
  REPO_URL = repo.split("~",1)[1]
  url = "http://consul.chilyard.int.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/branch?raw".format(REPO_NAME)
  response = requests.get(url)
  BRANCH = response.text
  subprocess.run(["git", "clone", REPO_URL, "/var/jenkins_home/jobs/jenkins-init", "--branch", BRANCH])

