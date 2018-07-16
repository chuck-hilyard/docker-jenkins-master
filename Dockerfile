FROM jenkins/jenkins:latest

USER root

COPY plugins.txt /usr/share/jenkins/ref/plugins.txt
RUN /usr/local/bin/install-plugins.sh < /usr/share/jenkins/ref/plugins.txt

ENV JENKINS_USER admin
ENV JENKINS_PASS admin

# Skip initial setup
ENV JAVA_OPTS -Djenkins.install.runSetupWizard=false

COPY executors.groovy /usr/share/jenkins/ref/init.groovy.d/
COPY default-user.groovy /usr/share/jenkins/ref/init.groovy.d/

VOLUME /var/jenkins_home

RUN apt-get -y update && apt-get -y upgrade && apt-get -y install python3 vim

RUN cd /tmp; git clone https://github.com/chuck-hilyard/docker-jenkins-master

USER jenkins
