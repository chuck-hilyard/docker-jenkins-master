# this is called by docker run
#
# starts jenkins
# installs plugins
# adds github based projects to jenkins/jobs

import consulate
import http.client
import jenkins
import requests
import subprocess
import time

def jenkins_start():
  # startup the jenkins service
  params = [ 'java', '-jar', '-Djenkins.install.runSetupWizard=false', '-Dpermissive-script-security.enabled=true', '/usr/share/jenkins/jenkins.war']
  jenkins_start = subprocess.Popen(params, stdout=subprocess.PIPE)

def install_software():
  # install the suggested and desired plugins list
  f = open('/tmp/docker-jenkins-master/plugins.txt', 'r')
  suggested_plugins = []
  for line in f:
    stripped = line.strip()
    suggested_plugins.append(stripped)
  # we're waiting 30 seconds for jenkins to come up
  # TODO: move this to a health check
  time.sleep(30)
  i = 0
  while i < len(suggested_plugins):
    PLUGIN = suggested_plugins[i]
    subprocess.run(["java", "-jar", "/var/jenkins_home/war/WEB-INF/jenkins-cli.jar", "-s", "http://127.0.0.1:8080/", "-auth", "admin:admin", "install-plugin", PLUGIN])
    i += 1

  # install build/test software
  # ***** make sure the previous install is done prior to moving on
  subprocess.run(["curl -sL https://deb.nodesource.com/setup_10.x |sudo -E bash -"], shell=True)
  time.sleep(15)
  subprocess.run(["sudo", "apt-get", "install", "-y", "awscli"])

  # add github repos as jobs to this jenkins server
  subprocess.run(["ssh-keyscan", "github.com", ">>", "/var/jenkins_home/.ssh/known_hosts"])
  f = open('/tmp/docker-jenkins-master/repos.txt', 'r')
  repos = []
  for repo in f:
    REPO_NAME = repo.split("~",1)[0].rstrip('\n')
    REPO_URL = repo.split("~",1)[1].rstrip('\n')
    TARGET_FOLDER = "/var/jenkins_home/jobs/{}".format(REPO_NAME)
    url = "http://consul:8500/v1/kv/{}/config/branch?raw".format(REPO_NAME)
    print("target url is ", url)
    response = requests.get(url)
    if response.status_code == 200:
      BRANCH = response.text
    else:
      BRANCH = "master"
    try:
      # ********* don't need to clone the repo, just place the config.xml file
      REPO_CONFIG_FILE_DIR = "/var/jenkins_home/jobs/{}/config.xml".format(REPO_NAME)
      subprocess.run(["git", "clone", REPO_URL, TARGET_FOLDER, "--branch", BRANCH, "--depth", "1"])
    except:
      print("git clone of {} failed, skipping...".format(REPO_NAME))
    try:
      template_repo_config_file = open('/tmp/docker-jenkins-master/template_repo_config.xml', 'r')
      template_repo_config_string = template_repo_config_file.read()
      template_repo_config_file.close()
      formatted_template = template_repo_config_string.format(REPO_URL=REPO_URL, BRANCH=BRANCH)
      repo_config_xml = open(REPO_CONFIG_FILE_DIR, 'w')
      repo_config_xml.write(formatted_template)
      repo_config_xml.close()
    except FileNotFoundError as e:
      print("file copy to {} failed".format(REPO_CONFIG_FILE_DIR))

  # process template_credentials.xml
  try:
    private_key_file = open('/var/jenkins_home/.ssh/id_rsa', 'r')
    PRIVATE_KEY_TMP = private_key_file.read()
    PRIVATE_KEY = PRIVATE_KEY_TMP.strip('\n')
  except FileNotFoundError as e:
    print("private key file not found")
  try:
    template_credentials_file = open('/tmp/docker-jenkins-master/template_credentials.xml', 'r')
    template_credentials_string_tmp = template_credentials_file.read()
    template_credentials_string = template_credentials_string_tmp.strip()
    template_credentials_file.close()
    formatted_template = template_credentials_string.format(PRIVATE_KEY=PRIVATE_KEY)
    credentials_xml_file = open('/var/jenkins_home/credentials.xml', 'w')
    credentials_xml_file.write(formatted_template)
    credentials_xml_file.close()
  except FileNotFoundError as e:
    print("file copy to credentials.xml failed")

  # after all the changes, hit restart
  subprocess.run(["curl", "-X", "POST", "-u", "admin:admin", "http://127.0.0.1:8080/safeRestart"])

def add_to_master(id, address, port):
  print("adding server to jenkins master: ", id, address, port)
  server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  params = {
    'port': port,
    'username': 'jenkins',
    'credentialsId': 'jenkins-credential-id',
    'host': address
  }
  try:
    server.create_node(
      id,
      nodeDescription = "test slave node",
      remoteFS        = "/var/jenkins_home",
      labels          = "common",
      exclusive       = False,
      launcher        = jenkins.LAUNCHER_SSH,
      launcher_params = params )
  except Exception as e:
    print("jenkins general exception: {}".format(e))

def remove_agent_from_master():
  print("checking for offline nodes")
  try:
    server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
    server_list = server.get_nodes()
    for dic in server_list:
      if dic['offline'] == True:
        print("{} is offline, removing".format(dic['name']))
        server.delete_node(dic['name'])
  except:
    print("jenkins general exception")

def scrape_consul():
  print("scraping consul")
  url = "http://consul:8500/v1/catalog/service/media-team-devops-automation-jenkins-agent"
  response = requests.get(url)

  if response.status_code != 200:
    print("consul scrape failed!  waiting for next run")

  for x in response.json():
    raw_id      = x["Address"]
    raw_address = x["Address"]
    raw_port    = x["ServicePort"]
    id = raw_id.replace('\r','')
    address = raw_address.replace('\r','')
    port = raw_port
    add_to_master(id, address, port)


def main():
  # dumb method to keep the this.process alive (may not be needed in a main loop)
  #jenkins_start.wait()
  while True:
    print("main loop")
    scrape_consul()
    remove_agent_from_master()
    time.sleep(60)


if __name__ == '__main__':
  jenkins_start()
  install_software()
  print("starting main()")
  main()
