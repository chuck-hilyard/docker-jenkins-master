# this gives you a base jenkins installation configured for our environment
# the actual jenkins setup/config happens in the init script (see CMD)
FROM jenkins/jenkins:latest

USER root

RUN /usr/local/bin/install-plugins.sh git matrix-auth workflow-aggregator docker-workflow blueocean credentials-binding 

ENV JENKINS_USER admin
ENV JENKINS_PASS admin
ENV CHROME_BIN /usr/bin/chromium

RUN apt-get -y update && apt-get -y upgrade && apt-get -y install python3 python3-jenkins python3-pip python3-boto3 vim sudo
RUN pip3 install requests

COPY --chown=jenkins *.groovy /usr/share/jenkins/ref/init.groovy.d/
COPY --chown=jenkins *.xml /var/jenkins_home/
COPY --chown=root id_rsa /root/.ssh/id_rsa
COPY --chown=jenkins id_rsa /var/jenkins_home/.ssh/id_rsa
COPY --chown=root known_hosts /root/.ssh/known_hosts
COPY --chown=jenkins known_hosts /var/jenkins_home/.ssh/known_hosts

RUN cd /tmp; git clone https://github.com/chuck-hilyard/docker-jenkins-master
RUN chown -R jenkins:jenkins /var/jenkins_home/; chown -R jenkins:jenkins /tmp
RUN echo "jenkins  ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/README

#VOLUME /var/jenkins_home

USER jenkins

CMD [ "python3", "-u", "/tmp/docker-jenkins-master/init.py" ]
