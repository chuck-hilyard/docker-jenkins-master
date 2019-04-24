# this gives you a base jenkins installation configured for our environment
# the actual jenkins setup/config happens in the init script (see CMD)
#FROM jenkins/jenkins:latest
FROM jenkins/jenkins:lts
#COPY jenkins.war.2.151 /usr/share/jenkins/jenkins.war
COPY jenkins.war.2.167 /usr/share/jenkins/jenkins.war

USER root

# removed blueocean (many dependencies) as it was breaking the build, moved it to init.py
RUN /usr/local/bin/install-plugins.sh git matrix-auth workflow-aggregator docker-workflow credentials-binding 

ENV JENKINS_USER admin
ENV JENKINS_PASS admin
ENV CHROME_BIN /usr/bin/chromium

RUN echo "deb http://ftp.de.debian.org/debian testing main" >> /etc/apt/sources.list
RUN apt-get -y update && apt-get -y upgrade && apt-get -y install python3 python3-pip python3-boto3 vim sudo
RUN apt-get -y install python3-jenkins=0.4.16-1 -V
RUN pip3 install requests consulate

COPY --chown=jenkins *.groovy /usr/share/jenkins/ref/init.groovy.d/
COPY --chown=jenkins *.xml /var/jenkins_home/
COPY --chown=root id_rsa /root/.ssh/id_rsa
COPY --chown=jenkins id_rsa /var/jenkins_home/.ssh/id_rsa
COPY --chown=root known_hosts /root/.ssh/known_hosts
COPY --chown=jenkins known_hosts /var/jenkins_home/.ssh/known_hosts
COPY --chown=jenkins ssh-slaves.1.28.1.hpi /tmp/ssh-slaves.hpi

RUN cd /tmp; git clone https://github.com/chuck-hilyard/docker-jenkins-master
RUN chown -R jenkins:jenkins /var/jenkins_home/; chown -R jenkins:jenkins /tmp
RUN echo "jenkins  ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/README
#RUN chmod 600 /var/jenkins_home/.ssh/id_rsa

#VOLUME /var/jenkins_home

#USER jenkins

COPY init.py /tmp/docker-jenkins-master/init.py
COPY Docker-entrypoint.sh /usr/local/bin/
ENTRYPOINT ["Docker-entrypoint.sh"]

CMD [ "python3", "-u", "/tmp/docker-jenkins-master/init.py" ]
