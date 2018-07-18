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

# add github repos to this jenkins server
f = open('/tmp/docker-jenkins-master/repos.txt', 'r')
repos = []
for repo in f:
  REPO_NAME = repo.split(str="~").strip()
  REPO_URL = repo.split(str="~").strip()
  url = "http://consul.chilyard.int.media.dev.usa.reachlocalservices.com:8500/v1/kv/{}/config/branch?raw".format(REPO_NAME)
  response = requests.get(url)
  BRANCH = response.text
  subprocess.run(["git", "clone", REPO_URL, "/var/jenkins_home/jobs/jenkins-init", "--branch", BRANCH])

# after all the changes, hit restart
subprocess.run(["curl", "-X", "POST", "-u", "admin:admin", "http://127.0.0.1:8080/safeRestart"])

# dumb method to keep the this.process alive
jenkins_start.wait()
