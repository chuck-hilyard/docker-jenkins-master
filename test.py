#!/usr/bin/env python3

import jenkins
import requests

def add_agent_to_master(id, address, port):
  print("adding server to jenkins master: ", id, address, port)
  server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  params = {
    'port': port,
    'username': 'jenkins',
    'credentialsId': 'jenkins-credential-id',
    'host': address,
    'javaPath': '/usr/bin/java'
  }
  try:
    server.create_node(
      id,
      nodeDescription = "test slave node",
      remoteFS = "/var/jenkins_home",
      labels = "common",
      exclusive = False,
      launcher = jenkins.LAUNCHER_SSH,
      launcher_params = params )
  except:
    print("jenkins exception catchall")

def remove_agent_from_master():
  print("checking for offline nodes")
  server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  server_list = server.get_nodes()
  for dic in server_list:
    if dic['offline'] == True:
      print("{} is offline, removing".format(dic['name']))
      server.delete_node(dic['name'])

def scrape_consul():
  print("scraping consul")
  url = "http://consul:8500/v1/catalog/service/media-team-devops-automation-jenkins-agent"
  response = requests.get(url)

  if response.status_code != 200:
    print("consul scrape failed!  waiting for next run")

  for x in response.json():
    raw_id      = x["ID"]
    raw_address = x["Address"]
    raw_port    = x["ServicePort"]
    id = raw_id.replace('\r',"")
    address = raw_address.replace('\r',"")
    port = raw_port
    add_agent_to_master(id, address, port)


print("start")
scrape_consul()
#remove_agent_from_master()
