# this is called by docker run
#
# starts jenkins
# installs plugins
# adds github based projects to jenkins/jobs

import http.client
import requests
import subprocess
import time

# add jenkins user to sudoers
jenkins_sudoers = "jenkins	ALL=(ALL) NOPASSWD: ALL"
sudoers_file = open('/etc/sudoers.d/jenkins', 'w')
sudoers_file.write(jenkins_sudoers)
sudoers_file.close()


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
subprocess.run(["sudo curl -sL https://deb.nodesource.com/setup_10.x |bash -"], shell=True)
time.sleep(15)
subprocess.run(["sudo", "apt-get", "install", "-y", "nodejs"])
time.sleep(15)
# TODO: verify npm is installed
subprocess.run(["sudo", "apt-get", "install", "-y", "chromium"])
time.sleep(15)
subprocess.run(["sudo", "apt-get", "install", "-y", "libgconf2-4"])
subprocess.run(["sudo", "apt-get", "install", "-y", "awscli"])
#subprocess.run(["usermod", "-aG", "docker", "jenkins"])
time.sleep(15)
subprocess.run(["sudo", "npm", "install", "-g", "gulp"])

# add github repos as jobs to this jenkins server
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
    REPO_CONFIG_FILE_DIR = "/var/jenkins_home/jobs/{}/config.xml".format(REPO_NAME)
    subprocess.run(["git", "clone", REPO_URL, TARGET_FOLDER, "--branch", BRANCH, "--depth", "1"])
  except:
    print("git clone of {} failed, skipping...".format(REPO_NAME))
  try:
    template_repo_config_file = open('/tmp/docker-jenkins-master/template_repo_config.xml', 'r')
    template_repo_config_string = template_repo_config_file.read()
    template_repo_config_file.close()
    formatted_template = template_repo_config_string.format(REPO_URL=REPO_URL, BRANCH=BRANCH)
    print("****************************** writing config.xml *********************")
    print("formatted_template: ", formatted_template)
    print("CONFIG FILE DIR: ", REPO_CONFIG_FILE_DIR)
    repo_config_xml = open(REPO_CONFIG_FILE_DIR, 'w')
    repo_config_xml.write(formatted_template)
    repo_config_xml.close()
  except FileNotFoundError as e:
    print("file copy to {} failed".format(REPO_CONFIG_FILE_DIR))

# after all the changes, hit restart
subprocess.run(["curl", "-X", "POST", "-u", "admin:admin", "http://127.0.0.1:8080/safeRestart"])

# dumb method to keep the this.process alive
jenkins_start.wait()
