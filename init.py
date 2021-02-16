# this is called by docker run
#
# starts jenkins
# installs plugins
# adds github based projects to jenkins/jobs

import glob
import jenkins
import json
import requests
import subprocess
import time

from socket import gaierror

multibranch_job_list = []

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

MULTIBRANCH_CONFIG_XML_TEMPLATE = '''<?xml version='1.1' encoding='UTF-8'?>
<org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject plugin="workflow-multibranch@2.22">
  <actions/>
  <description></description>
  <properties>
    <org.jenkinsci.plugins.docker.workflow.declarative.FolderConfig plugin="docker-workflow@1.25">
      <dockerLabel></dockerLabel>
      <registry plugin="docker-commons@1.16"/>
    </org.jenkinsci.plugins.docker.workflow.declarative.FolderConfig>
  </properties>
  <folderViews class="jenkins.branch.MultiBranchProjectViewHolder" plugin="branch-api@2.6.2">
    <owner class="org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject" reference="../.."/>
  </folderViews>
  <healthMetrics>
    <com.cloudbees.hudson.plugins.folder.health.WorstChildHealthMetric plugin="cloudbees-folder@6.14">
      <nonRecursive>false</nonRecursive>
    </com.cloudbees.hudson.plugins.folder.health.WorstChildHealthMetric>
  </healthMetrics>
  <icon class="jenkins.branch.MetadataActionFolderIcon" plugin="branch-api@2.6.2">
    <owner class="org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject" reference="../.."/>
  </icon>
  <orphanedItemStrategy class="com.cloudbees.hudson.plugins.folder.computed.DefaultOrphanedItemStrategy" plugin="cloudbees-folder@6.14">
    <pruneDeadBranches>true</pruneDeadBranches>
    <daysToKeep>-1</daysToKeep>
    <numToKeep>-1</numToKeep>
  </orphanedItemStrategy>
  <triggers>
    <com.cloudbees.hudson.plugins.folder.computed.PeriodicFolderTrigger plugin="cloudbees-folder@6.14">
      <spec>* * * * *</spec>
      <interval>300000</interval>
    </com.cloudbees.hudson.plugins.folder.computed.PeriodicFolderTrigger>
  </triggers>
  <disabled>false</disabled>
  <sources class="jenkins.branch.MultiBranchProject$BranchSourceList" plugin="branch-api@2.6.2">
    <data>
      <jenkins.branch.BranchSource>
        <source class="jenkins.plugins.git.GitSCMSource" plugin="git@4.2.2">
          <id>8171e18e-f660-49f6-94d5-54c747d37a3f</id>
          <remote>{REPO_URL}</remote>
          <credentialsId>jenkins-credential-id</credentialsId>
          <traits>
            <jenkins.plugins.git.traits.BranchDiscoveryTrait/>
          </traits>
        </source>
        <strategy class="jenkins.branch.DefaultBranchPropertyStrategy">
          <properties class="empty-list"/>
        </strategy>
      </jenkins.branch.BranchSource>
    </data>
    <owner class="org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject" reference="../.."/>
  </sources>
  <factory class="org.jenkinsci.plugins.workflow.multibranch.WorkflowBranchProjectFactory">
    <owner class="org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject" reference="../.."/>
    <scriptPath>{JENKINSFILE}</scriptPath>
  </factory>
</org.jenkinsci.plugins.workflow.multibranch.WorkflowMultiBranchProject>'''


def jenkins_start():
  # startup the jenkins service
  params = [ 'java', '-jar', '-Djenkins.install.runSetupWizard=false', '-Dpermissive-script-security.enabled=true', '/usr/share/jenkins/jenkins.war']
  jenkins_start = subprocess.Popen(params, stdout=subprocess.PIPE)


def install_software():
  # we're waiting for jenkins to come up
  # TODO: move this to a health check
  time.sleep(30)

  # TODO: this is from a merge conflict during 2_263 upgrade (do we need this?)
  print("DOWNLOADING jenkins-cli.jar")
  subprocess.run(["wget", "-P", "/var/jenkins_home/war/WEB-INF", "http://127.0.0.1:8080/jnlpJars/jenkins-cli.jar"])

  # install plugins downloaded during docker build
  docker_build_plugins = glob.glob('/tmp/plugins/*')
  docker_build_plugins_list = []
  for line in list(docker_build_plugins):
    docker_build_plugins_list.append(line)
  i = 0
  while i < len(docker_build_plugins_list):
    PLUGIN = docker_build_plugins_list[i]
    print("installing downloaded PLUGIN {}:".format(PLUGIN))
    subprocess.run(["java", "-jar", "/var/jenkins_home/war/WEB-INF/jenkins-cli.jar", "-s", "http://127.0.0.1:8080/", "-auth", "admin:11fdf46a3db182d421efbf077f7974f3aa", "install-plugin", "file://{}".format(PLUGIN)])
    i += 1

  # install the suggested and desired plugins list
  f = open('/tmp/docker-jenkins-master/plugins.txt', 'r')
  suggested_plugins = []
  for line in f:
    stripped = line.strip()
    suggested_plugins.append(stripped)

  i = 0
  while i < len(suggested_plugins):
    PLUGIN = suggested_plugins[i]
    print("installing from plugin.txt {}".format(PLUGIN))
    subprocess.run(["java", "-jar", "/var/jenkins_home/war/WEB-INF/jenkins-cli.jar", "-s", "http://127.0.0.1:8080/", "-auth", "admin:11fdf46a3db182d421efbf077f7974f3aa", "install-plugin", PLUGIN])
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

  # mv config_xml into config.xml
  subprocess.run(["cp", "/var/jenkins_home/config_xml", "/var/jenkins_home/config.xml"])

  # after all the changes, hit restart
  print("SLEEPING 30 BEFORE RESTART")
  time.sleep(30)
  #subprocess.run(["curl", "-X", "POST", "-u", "admin:11fdf46a3db182d421efbf077f7974f3aa", "http://127.0.0.1:8080/safeRestart"])
  subprocess.run(["java", "-jar", "/var/jenkins_home/war/WEB-INF/jenkins-cli.jar", "-s", "http://127.0.0.1:8080/", "safe-restart"])


def add_agent_to_master(id, address, port):
  print("adding server to jenkins master: ", id, address, port)
  try:
    server = jenkins.Jenkins('http://127.0.0.1:8080', username='admin', password='11fdf46a3db182d421efbf077f7974f3aa')
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
    server = jenkins.Jenkins('http://127.0.0.1:8080', username='admin', password='11fdf46a3db182d421efbf077f7974f3aa')
  except Exception as ex:
    print("exception when connecting to jenkins master (localhost): {}".format(ex))
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
    server = jenkins.Jenkins('http://127.0.0.1:8080', username='admin', password='11fdf46a3db182d421efbf077f7974f3aa')
  except Exception as ex:
    print("exception when removing agent from jenkins master: {}".format(ex))
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


def scrape_consul_for_deploy_jobs_to_add():
  print("scraping consul for deploy jobs to add")
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
        #deploy_type_url = "https://consul.dev.usa.media.reachlocalservices.com/v1/kv/{}/config/deploy_type?raw".format(project_name)
        try:
          response_deploy_type_url = requests.get(deploy_type_url)
        except:
          print("failed trying to get DEPLOY_TYPE for {}".format(project_name))
          return
        branch_url = "http://consul:8500/v1/kv/{}/config/branch?raw".format(project_name)
        #branch_url = "https://consul.dev.usa.media.reachlocalservices.com/v1/kv/{}/config/branch?raw".format(project_name)
        response_branch_url = requests.get(branch_url)
        branch = response_branch_url.text

        github_url = "http://consul:8500/v1/kv/{}/config/github_repo?raw".format(project_name)
        #github_url = "https://consul.dev.usa.media.reachlocalservices.com/v1/kv/{}/config/github_repo?raw".format(project_name)
        response_github_url = requests.get(github_url)
        github_repo = response_github_url.text

        jenkinsfile_url = "http://consul:8500/v1/kv/{}/config/jenkinsfile?raw".format(project_name)
        #jenkinsfile_url = "https://consul.dev.usa.media.reachlocalservices.com/v1/kv/{}/config/jenkinsfile?raw".format(project_name)
        response_jenkinsfile_url = requests.get(jenkinsfile_url)
        jenkinsfile = response_jenkinsfile_url.text
        if (len(jenkinsfile) == 0):
          jenkinsfile = "Jenkinsfile"

        multibranch_url = "http://consul:8500/v1/kv/{}/config/multibranch?raw".format(project_name)
        #multibranch_url = "https://consul.dev.usa.media.reachlocalservices.com/v1/kv/{}/config/multibranch?raw".format(project_name)
        response_multibranch_url = requests.get(multibranch_url)
        multibranch = response_multibranch_url.text

        print("project_name: ", project_name)
        print("jenkinsfile: ", jenkinsfile)
        print("response_deploy_type_url: ", response_deploy_type_url.text)

        if response_deploy_type_url.text == 'gitflow' and response_multibranch_url.text == 'true':
          try:
            print("create multbranch pipeline jenkins job for ", project_name)
            create_multibranch_pipeline_job(project_name, github_repo, branch, jenkinsfile)
          except jenkins.JenkinsException as e:
            print("found {}, updating".format(e))
            update_multibranch_job(project_name, github_repo, branch, jenkinsfile)
        elif response_deploy_type_url.text == 'gitflow':
          if current_multibranch_jobs('check', project_name) > 0:
            print("removing multibranch pipeline jenkins job for ", project_name)
            remove_jenkins_job(project_name)
            print("create jenkins job for ", project_name)
            create_jenkins_job(project_name, github_repo, branch, jenkinsfile)
          else:
            print("update jenkins job for ", project_name)
            #create_jenkins_job(project_name, github_repo, branch, jenkinsfile)
            update_jenkins_job(project_name, github_repo, branch, jenkinsfile)
        else:
          pass


def current_multibranch_jobs(action, name):
  if action == 'check':
    return multibranch_job_list.count(name)
  elif action == 'add':
    multibranch_job_list.append(name)
  elif action == 'remove':
    multibranch_job_list.remove(name)


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
        #deploy_type_url = "https://consul.dev.usa.media.reachlocalservices.com/v1/kv/{}/config/deploy_type?raw".format(project_name)
        try:
          response_deploy_type_url = requests.get(deploy_type_url)
        except:
          print("failed trying to get deploy_type for {}".format(project_name))
          return

        #runonce_url = "http://consul:8500/v1/kv/{}/config/runonce?raw".format(project_name)
        #runonce_url = "https://consul.dev.usa.media.reachlocalservices.com/v1/kv/{}/config/runonce?raw".format(project_name)
        #response_runonce_url = requests.get(runonce_url)

        if response_deploy_type_url.text != 'gitflow':
          try:
            print("remove jenkins job for {}", project_name)
            remove_jenkins_job(project_name)
            #remove_consul_entry(project_name)
          except jenkins.JenkinsException as e:
            print("exception removing jenkins job {}".format(e))
        else:
          pass


def update_jenkins_job(name, github_repo, branch, jenkinsfile='Jenkinsfile'):
  print("update_jenkins_job()")
  try:
    server = jenkins.Jenkins('http://127.0.0.1:8080', username='admin', password='11fdf46a3db182d421efbf077f7974f3aa')
  except Exception as ex:
    print("exception when updating job {}: {}".format(name, ex))
    return
  BASE_CONFIG_XML_FORMATTED_TEMPLATE = BASE_CONFIG_XML_TEMPLATE.format(REPO_URL=github_repo, BRANCH=branch, JENKINSFILE=jenkinsfile)
  server.reconfig_job(name, BASE_CONFIG_XML_FORMATTED_TEMPLATE)


def update_multibranch_job(name, github_repo, branch, jenkinsfile='Jenkinsfile'):
  print("updating multibranch jenkins job for {}".format(name))
  try:
    server = jenkins.Jenkins('http://127.0.0.1:8080', username='admin', password='11fdf46a3db182d421efbf077f7974f3aa')
  except Exception as ex:
    print("exception when updating multibranch job {}: {}".format(name, ex))
    return
  MULTIBRANCH_CONFIG_XML_FORMATTED_TEMPLATE = MULTIBRANCH_CONFIG_XML_TEMPLATE.format(REPO_URL=github_repo, BRANCH=branch, JENKINSFILE=jenkinsfile)
  server.reconfig_job(name, MULTIBRANCH_CONFIG_XML_FORMATTED_TEMPLATE)


def remove_jenkins_job(project_name):
  print("removing {} job from jenkins".format(project_name))
  server = jenkins.Jenkins('http://127.0.0.1:8080', username='admin', password='11fdf46a3db182d421efbf077f7974f3aa')
  running_builds = server.get_running_builds()
  print("RUNNING BUILDS: ", running_builds)
  try:
    server.delete_job(project_name)
  except jenkins.NotFoundException as jnfe:
    print("exception when removing job {} from jenkins master: {}".format(project_name, jnfe))
    return


def create_jenkins_job(name, github_repo, branch, jenkinsfile='Jenkinsfile'):
  print("in create_jenkins_job")
  try:
    server = jenkins.Jenkins('http://127.0.0.1:8080', username='admin', password='11fdf46a3db182d421efbf077f7974f3aa')
  except Exception as ex:
    print("exception when adding job to jenkins master: {}".format(ex))
    return
  BASE_CONFIG_XML_FORMATTED_TEMPLATE = BASE_CONFIG_XML_TEMPLATE.format(REPO_URL=github_repo, BRANCH=branch, JENKINSFILE=jenkinsfile)

  out = None
  try:
    out = server.get_job_config(name)
  except jenkins.NotFoundException as nfe:
    print("not found exception doing get_job_config({}): {}".format(name, nfe))
    pass
  except Exception as ex:
    print("exception doing get_job_config({}): {}".format(name, ex))
    pass

  if out == None:
    server.create_job(name, BASE_CONFIG_XML_FORMATTED_TEMPLATE)
  elif current_multibranch_jobs('check', name) > 0:
    server.delete_job(name)
    current_multibranch_jobs('remove', project_name)
    server.create_job(name, BASE_CONFIG_XML_FORMATTED_TEMPLATE)
  else:
    pass


def create_multibranch_pipeline_job(name, github_repo, branch, jenkinsfile='Jenkinsfile'):
  try:
    server = jenkins.Jenkins('http://127.0.0.1:8080', username='admin', password='11fdf46a3db182d421efbf077f7974f3aa')
  except Exception as ex:
    print("exception when adding job to jenkins master: {}".format(ex))
    return
  # format the job configuration template
  MULTIBRANCH_CONFIG_XML_FORMATTED_TEMPLATE = MULTIBRANCH_CONFIG_XML_TEMPLATE.format(REPO_URL=github_repo, BRANCH=branch, JENKINSFILE=jenkinsfile)
  # if jobs already exists, delete it then create
  job_exists = None
  try:
    job_exists = server.get_job_config(name)
  except jenkins.NotFoundException as nfe:
    print("not found exception doing get_job_config({}): {}".format(name, nfe))
    pass
  except Exception as ex:
    print("exception doing multibranch.get_job_config({}): {}".format(name, ex))
    pass

  already_multibranch = current_multibranch_jobs('check', name)
  print("ALREADY MULTIBRANCH: {}".format(already_multibranch))

  if job_exists == None:
    print("CREATE JOB")
    server.create_job(name, MULTIBRANCH_CONFIG_XML_FORMATTED_TEMPLATE)
    current_multibranch_jobs('add', name)
  elif job_exists and already_multibranch != 1:
    server.delete_job(name)
    server.create_job(name, MULTIBRANCH_CONFIG_XML_FORMATTED_TEMPLATE)
  elif job_exists and already_multibranch == 1:
    print("RECONFIG JOB")
    server.reconfig_job(name, MULTIBRANCH_CONFIG_XML_FORMATTED_TEMPLATE)
  else:
    pass



def main():
  while True:
    print("main loop")
    scrape_consul_for_agents()
    time.sleep(30)
    scrape_consul_for_docker_engines()
    time.sleep(30)
    scrape_consul_for_deploy_jobs_to_add()
    time.sleep(30)
    scrape_consul_for_deploy_jobs_to_remove()
    time.sleep(30)
    scrape_consul_for_deploy_jobs_to_remove()
    time.sleep(30)
    remove_agent_from_master()
    time.sleep(30)


if __name__ == '__main__':
  jenkins_start()
  install_software()
  time.sleep(30)
  main()
