FROM jenkins/jenkins:latest

USER root

COPY plugins.txt /tmp/plugins.txt
RUN /usr/local/bin/install-plugins.sh git matrix-auth workflow-aggregator docker-workflow blueocean credentials-binding 

ENV JENKINS_USER admin
ENV JENKINS_PASS admin
ENV EXECUTOR_NUMBER 1
ENV SLAVE_EXECUTORS "1"

# Skip initial setup
ENV JAVA_OPTS -Djenkins.install.runSetupWizard=false

COPY executors.groovy /usr/share/jenkins/ref/init.groovy.d/
COPY default-user.groovy /usr/share/jenkins/ref/init.groovy.d/
#COPY init_config.xml /var/jenkins_home/jobs/init/config.xml

VOLUME /var/jenkins_home

RUN apt-get -y update && apt-get -y upgrade && apt-get -y install python3 vim

RUN cd /tmp; git clone https://github.com/chuck-hilyard/docker-jenkins-master

USER root

CMD [ "python3", "-u", "/tmp/docker-jenkins-master/init.py" ]
