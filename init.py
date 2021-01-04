# this is called by docker run
#
# starts jenkins
# installs plugins
# adds github based projects to jenkins/jobs

import consulate
import http.client
import jenkins
import json
import requests
import subprocess
import time

from socket import gaierror

BASE_CREDENTIALS_XML_TEMPLATE = '''<?xml version='1.1' encoding='UTF-8'?>
<com.cloudbees.plugins.credentials.SystemCredentialsProvider plugin="credentials@2.1.18">
  <domainCredentialsMap class="hudson.util.CopyOnWriteMap$Hash">
    <entry>
      <com.cloudbees.plugins.credentials.domains.Domain>
        <specifications/>
      </com.cloudbees.plugins.credentials.domains.Domain>
      <java.util.concurrent.CopyOnWriteArrayList/>
    </entry>
    <entry>
      <com.cloudbees.plugins.credentials.domains.Domain>
        <name>initial</name>
        <description>initial domain</description>
        <specifications/>
      </com.cloudbees.plugins.credentials.domains.Domain>
      <list>
        <com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey plugin="ssh-credentials@1.14">
          <scope>GLOBAL</scope>
          <id>jenkins-credential-id</id>
          <description></description>
          <username>jenkins</username>
          <privateKeySource class="com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey$DirectEntryPrivateKeySource">
            <privateKey>{PRIVATE_KEY}</privateKey>
          </privateKeySource>
        </com.cloudbees.jenkins.plugins.sshcredentials.impl.BasicSSHUserPrivateKey>
      </list>
    </entry>
  </domainCredentialsMap>
</com.cloudbees.plugins.credentials.SystemCredentialsProvider>'''

BASE_CONFIG_XML_TEMPLATE = '''<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job@2.25">
  <description></description>
  <keepDependencies>false</keepDependencies>
  <properties>
    <org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
      <triggers>
        <hudson.triggers.SCMTrigger>
          <spec>* * * * *</spec>
          <ignorePostCommitHooks>false</ignorePostCommitHooks>
        </hudson.triggers.SCMTrigger>
      </triggers>
    </org.jenkinsci.plugins.workflow.job.properties.PipelineTriggersJobProperty>
  </properties>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps@2.57">
    <scm class="hudson.plugins.git.GitSCM" plugin="git@3.9.1">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>{REPO_URL}</url>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/{BRANCH}</name>
        </hudson.plugins.git.BranchSpec>
      </branches>
      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      <submoduleCfg class="list"/>
      <extensions>
        <hudson.plugins.git.extensions.impl.WipeWorkspace/>
      </extensions>
    </scm>
    <scriptPath>{JENKINSFILE}</scriptPath>
    <lightweight>false</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>'''

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
  time.sleep(15)
  subprocess.run(["chmod", "600", "/var/jenkins_home/.ssh/id_rsa", "/root/.ssh/id_rsa"])

  # add github repos as jobs to this jenkins server
  # (this vestige creates a jenkins-init job which is used to verify a successful deploy of jenkins-master)
  subprocess.run(["ssh-keyscan", "github.com", ">>", "/var/jenkins_home/.ssh/known_hosts"])
  f = open('/tmp/docker-jenkins-master/repos.txt', 'r')
  repos = []
  for repo in f:
    REPO_NAME = repo.split("~",1)[0].rstrip('\n')
    REPO_URL = repo.split("~",1)[1].rstrip('\n')
    TARGET_FOLDER = "/var/jenkins_home/jobs/{}".format(REPO_NAME)
    url = "http://consul:8500/v1/kv/{}/config/branch?raw".format(REPO_NAME)
    print("target url is ", url)
    try:
      response = requests.get(url)
    except requests.exceptions.RequestException as e:
      print("exception talking to consul: {}".format(e))
      return
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

def add_agent_to_master(id, address, port):
  print("adding server to jenkins master: ", id, address, port)
  try:
    server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  except Exception as ex:
    print("exception when connecting adming to jenkins master: {}".format(ex))
    return
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
  except Exception as e:
    print("jenkins exception(adding server to jenkins master): {}".format(e))

def add_docker_engine_to_master(id, address, port):
  print("adding docker engine to jenkins master: ", id, address, port)
  try:
    server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  except Exception as ex:
    print("exception when adding docker engine to jenkins master: {}".format(ex))
    return
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
      nodeDescription = "jenkins agent docker builds",
      remoteFS = "/var/jenkins_home",
      labels = "docker-builds",
      exclusive = False,
      launcher = jenkins.LAUNCHER_SSH,
      launcher_params = params )
  except Exception as e:
    print("jenkins exception (adding docker engine to jenkins master): {}".format(e))

def remove_agent_from_master():
  print("checking for offline nodes")
  try:
    server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  except Exception as ex:
    print("exception when adding server to jenkins master: {}".format(ex))
    return
  try:
    server_list = server.get_nodes()
  except jenkins.JenkinsException as ex:
    return
  for dic in server_list:
    if dic['offline'] == True:
      print("{} is offline, removing".format(dic['name']))
      try:
        server.delete_node(dic['name'])
      except Exception as ex:
        print("exception while removing {} from jenkins master".format(ex))
        return

def scrape_consul_for_docker_engines():
  print("scraping consul for docker engines")
  # this is the consul service as reported by registrator.  as consul runs on each node in the cluster
  # it should accurately reflect the available nodes available for docker engine work
  url = "http://consul:8500/v1/catalog/service/media-team-devops-automation-jenkins-agent"
  try:
    response = requests.get(url)
  except requests.exceptions.RequestException as e:
    print("exception talking to consul: {}".format(e))
    return
  if response.status_code == 200:
    for x in response.json():
      raw_address = x["Address"]
      #raw_port    = x["ServicePort"]
      address = raw_address.replace('\r',"")
      port = 22
      id = "{}-{}".format(address, port)
      add_docker_engine_to_master(id, address, port)

def scrape_consul_for_agents():
  print("scraping consul for agents")
  url = "http://consul:8500/v1/catalog/service/media-team-devops-automation-jenkins-agent"
  try:
    response = requests.get(url)
  except requests.exceptions.RequestException as e:
    print("exception talking to consul: {}".format(e))
    return
  if response.status_code == 200:
    for x in response.json():
      raw_address = x["Address"]
      raw_port    = x["ServicePort"]
      address = raw_address.replace('\r',"")
      port = raw_port
      id = "{}-{}".format(address, port)
      add_agent_to_master(id, address, port)

def scrape_consul_for_deploy_jobs():
  print("scraping consul for deploy jobs")
  url = 'http://consul:8500/v1/kv/?keys&separator=/'
  try:
    response = requests.get(url)
  except requests.exceptions.RequestException as e:
    print("exception talking to consul: {}".format(e))
    return
  if response.status_code == 200:
    toplevel_keys_json = json.loads(response.text)

    for x in toplevel_keys_json:
        project_name = x.strip('/')
        deploy_type_url = "http://consul:8500/v1/kv/{}/config/deploy_type?raw".format(project_name)
        try:
          response_deploy_type_url = requests.get(deploy_type_url)
        except:
          print("failed trying to get DEPLOY_TYPE for {}".format(project_name))
          return
        branch_url = "http://consul:8500/v1/kv/{}/config/branch?raw".format(project_name)
        response_branch_url = requests.get(branch_url)
        branch = response_branch_url.text

        github_url = "http://consul:8500/v1/kv/{}/config/github_repo?raw".format(project_name)
        response_github_url = requests.get(github_url)
        github_repo = response_github_url.text

        jenkinsfile_url = "http://consul:8500/v1/kv/{}/config/jenkinsfile?raw".format(project_name)
        response_jenkinsfile_url = requests.get(jenkinsfile_url)
        jenkinsfile = response_jenkinsfile_url.text
        if (len(jenkinsfile) == 0):
          jenkinsfile = "Jenkinsfile"

        print("project_name: ", project_name)
        print("jenkinsfile: ", jenkinsfile)
        print("response_deploy_type_url: ", response_deploy_type_url.text)
        if response_deploy_type_url.text == 'gitflow':
          try:
            print("create jenkins job for ", project_name)
            create_jenkins_job(project_name, github_repo, branch, jenkinsfile)
          except jenkins.JenkinsException as e:
            print("found {}, updating".format(e))
            update_jenkins_job(project_name, github_repo, branch, jenkinsfile)
        else:
          remove_jenkins_job(project_name)

def scrape_consul_for_deploy_jobs_to_remove():
  print("scraping consul for deploy jobs to remove")
  url = 'http://consul:8500/v1/kv/?keys&separator=/'
  try:
    response = requests.get(url)
  except requests.exceptions.RequestException as e:
    print("exception talking to consul: {}".format(e))
    return
  if response.status_code == 200:
    toplevel_keys_json = json.loads(response.text)

    for x in toplevel_keys_json:
        project_name = x.strip('/')
        deploy_type_url = "http://consul:8500/v1/kv/{}/config/deploy_type?raw".format(project_name)
        try:
          response_deploy_type_url = requests.get(deploy_type_url)
        except:
          print("failed trying to get RUNONCE for {}".format(project_name))
          return

        runonce_url = "http://consul:8500/v1/kv/{}/config/runonce?raw".format(project_name)
        response_runonce = requests.get(runonce_url)
        runonce_state = response_runonce.text

        if runonce_state.text == 'true':
          try:
            print("remove jenkins job for {}", project_name)
            remove_jenkins_job(project_name)
          except jenkins.JenkinsException as e:
            print("exception removing jenkins job {}".format(e))
        else:
          pass

def update_jenkins_job(name, github_repo, branch, jenkinsfile='Jenkinsfile'):
  try:
    server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  except Exception as ex:
    print("exception when adding server to jenkins master: {}".format(ex))
    return
  BASE_CONFIG_XML_FORMATTED_TEMPLATE = BASE_CONFIG_XML_TEMPLATE.format(REPO_URL=github_repo, BRANCH=branch, JENKINSFILE=jenkinsfile)
  server.reconfig_job(name, BASE_CONFIG_XML_FORMATTED_TEMPLATE)

def remove_jenkins_job(project_name):
  print("removing {} job from jenkins".format(project_name))
  server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  try:
    server.delete_job(project_name)
  except jenkins.NotFoundException as jnfe:
    print("exception when removing job {} from jenkins master: {}".format(project_name, jnfe))
    return

def create_jenkins_job(name, github_repo, branch, jenkinsfile='Jenkinsfile'):
  try:
    server = jenkins.Jenkins('http://jenkins-master', username='admin', password='admin')
  except Exception as ex:
    print("exception when adding job to jenkins master: {}".format(ex))
    return
  # format the job configuration template
  BASE_CONFIG_XML_FORMATTED_TEMPLATE = BASE_CONFIG_XML_TEMPLATE.format(REPO_URL=github_repo, BRANCH=branch, JENKINSFILE=jenkinsfile)
  # if jobs exists, delete it the create
  server.create_job(name, BASE_CONFIG_XML_FORMATTED_TEMPLATE)

def main():
  while True:
    print("main loop")
    scrape_consul_for_agents()
    time.sleep(30)
    scrape_consul_for_docker_engines()
    time.sleep(30)
    scrape_consul_for_deploy_jobs()
    time.sleep(30)
    scrape_consul_for_deploy_jobs_to_remove()
    time.sleep(30)
    remove_agent_from_master()
    time.sleep(30)


if __name__ == '__main__':
  jenkins_start()
  install_software()
  main()
