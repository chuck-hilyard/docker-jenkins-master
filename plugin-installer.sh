#!/bin/bash

mkdir -p /tmp/plugins

#--skp-failed-plugins
plugins="git matrix-auth workflow-aggregator docker-workflow credentials-binding ant authentication-tokens aws-java-sdk blueocean branch-api build-timeout ssh-agent credentials docker-commons durable-task emailtext-template git-client git-server github-branch-source gradle http_request ldap matrix-project resource-disposer s3 saferestart scm-api ssh-credentials token-macro xvnc windows-slaves"

for plugin in ${plugins}
  do
    echo "********************   installing ${plugin}"
    /bin/jenkins-plugin-cli --plugin-download-directory /tmp/plugins --war /usr/share/jenkins/jenkins.war --plugins -p "$(echo ${plugin})"
    if [ $? -eq 0 ]
      then
        echo "********************   download of ${plugin} successful"

      else
        echo "********************   download of ${plugin} failed, retrying"
          until [ $? -eq 0 ]
            do
              echo "********************   retrying install of ${plugin}"
              /bin/jenkins-plugin-cli --plugin-download-directory /tmp/plugin --plugins --war /usr/share/jenkins/jenkins.war -p $(echo ${plugin})
            done
    fi
    echo "********************   DONE installing ${plugin}"
done
