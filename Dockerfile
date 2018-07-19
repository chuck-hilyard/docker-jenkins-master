FROM jenkins/jenkins:latest

USER root

COPY plugins.txt /tmp/plugins.txt
RUN /usr/local/bin/install-plugins.sh git matrix-auth workflow-aggregator docker-workflow blueocean credentials-binding 

ENV JENKINS_USER admin
ENV JENKINS_PASS admin

COPY executors.groovy /usr/share/jenkins/ref/init.groovy.d/
COPY default-user.groovy /usr/share/jenkins/ref/init.groovy.d/
COPY *.xml /var/jenkins_home/
COPY aws_codebuild /var/jenkins_home/.ssh/aws_codebuild; chown jenkins:jenkins ~/.ssh/aws_codebuild

VOLUME /var/jenkins_home

RUN apt-get -y update && apt-get -y upgrade && apt-get -y install python3 python3-jenkins python3-pip vim
RUN pip3 install requests

RUN cd /tmp; git clone https://github.com/chuck-hilyard/docker-jenkins-master
RUN chown jenkins:jenkins /var/jenkins_home/*.xml

USER jenkins


CMD [ "python3", "-u", "/tmp/docker-jenkins-master/init.py" ]
