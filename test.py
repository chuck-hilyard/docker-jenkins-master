#!/usr/bin/env python3

import jenkins
import json
import requests

#curl -X GET http://consul.chilyard.media.dev.usa.reachlocalservices.com:8500/v1/catalog/service/media-team-devops-automation-jenkins-agent

def add_to_master(id, address, port):
  print("adding server to jenkins master: ", id, address, port)
  server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  params = {
    'port': port,
    'username': 'jenkins',
    'credentialsId': 'jenkins-credential-id',
    'host': address
  }
  server.create_node(
    'blah',
    nodeDescription = "test slave node",
    remoteFS        = "/var/jenkins_home",
    labels          = "common",
    exclusive       = False,
    launcher        = jenkins.LAUNCHER_SSH,
    launcher_params = params )

url = "http://consul:8500/v1/catalog/service/media-team-devops-automation-jenkins-agent"
response = requests.get(url)

if response.status_code != 200:
  print("consul scrape failed!  waiting for next run")


for x in response.json():
  id      = x["ID"]
  address = x["Address"]
  port    = x["ServicePort"]
  add_to_master(id, address, port)
