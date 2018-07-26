# this is called by docker run
#
# starts jenkins
# installs plugins
# adds github based projects to jenkins/jobs

import http.client
import requests
import subprocess
import time

# startup the jenkins service
params = [ 'java', '-jar', '-Djenkins.install.runSetupWizard=false', '/usr/share/jenkins/jenkins.war']
jenkins_start = subprocess.Popen(params, stdout=subprocess.PIPE)

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
#subprocess.run(["sudo", "apt-get", "install", "-y", "nodejs"])
#time.sleep(15)
# TODO: verify npm is installed
#subprocess.run(["sudo", "apt-get", "install", "-y", "chromium"])
#time.sleep(15)
#subprocess.run(["sudo", "apt-get", "install", "-y", "libgconf2-4"])
#time.sleep(15)
subprocess.run(["sudo", "apt-get", "install", "-y", "awscli"])
#subprocess.run(["usermod", "-aG", "docker", "jenkins"])
#time.sleep(15)
#subprocess.run(["sudo", "npm", "install", "-g", "gulp"])

# add github repos as jobs to this jenkins server
subprocess.run(["ssh-keyscan", "github.com", ">>", "/var/jenkins_home/.ssh/known_hosts"])
f = open('/tmp/docker-jenkins-master/repos.txt', 'r')
repos = []
for repo in f:
  REPO_NAME = repo.split("~",1)[0].rstrip('\n')
  REPO_URL = repo.split("~",1)[1].rstrip('\n')
  TARGET_FOLDER = "/var/jenkins_home/jobs/{}".format(REPO_NAME)
  url = "http://consul.chilyard.int.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/branch?raw".format(REPO_NAME)
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
  print("********************************************************************************")
  print("PRIVATE KEY is ", type(PRIVATE_KEY))
  print("PRIVATE KEY: {}".format(PRIVATE_KEY))
  print("********************************************************************************")
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

# dumb method to keep the this.process alive
jenkins_start.wait()
