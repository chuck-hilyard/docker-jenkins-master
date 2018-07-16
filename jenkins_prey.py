#!/usr/bin/env python3


f = open('/tmp/suggested_plugins.txt', 'r')

suggested_plugins = []

for line in f:
  stripped = line.strip()
  suggested_plugins.append(stripped)

i = 0
while i < len(suggested_plugins):
  print(suggested_plugins[i])
  i += 1
#java -jar /var/lib/jenkins/jenkins.war -s http://127.0.0.1:8080/ install-plugin ${Plugin_Name}
