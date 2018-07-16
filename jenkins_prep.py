#!/usr/bin/env python3

# set the initial admin password (doesn't change until jenkins is setup)
f = open('/root/.jenkins/secrets/initialAdminPassword')
f.strip()
initialAdminPassword = f.readline()


# setup the suggested and desired plugins list
f = open('/tmp/suggested_plugins.txt', 'r')
suggested_plugins = []
for line in f:
  stripped = line.strip()
  suggested_plugins.append(stripped)


i = 0
while i < len(suggested_plugins):
  print("installing {0}".format(suggested_plugins[i]))
  i += 1
  java -jar WEB-INF/jenkins-cli.jar -s http://127.0.0.1:8080/ -auth admin:{0} install-plugin CCM
