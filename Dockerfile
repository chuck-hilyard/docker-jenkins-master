# this gives you a base jenkins installation configured for our environment
# the actual jenkins setup/config happens in the init script (see CMD)
FROM jenkins/jenkins:lts-jdk8

USER root

ENV DEBIAN_FRONTEND noninteractive

RUN wget -nv -O /usr/share/jenkins/jenkins.war updates.jenkins-ci.org/download/war/2.266/jenkins.war

# removed blueocean (many dependencies) as it was breaking the build, moved it to init.py
RUN /usr/local/bin/install-plugins.sh git matrix-auth workflow-aggregator docker-workflow credentials-binding 

ENV JENKINS_USER admin
ENV JENKINS_PASS admin
ENV CHROME_BIN /usr/bin/chromium
ENV USERNAME admin
ENV PASSWORD admin

RUN echo "deb http://ftp.de.debian.org/debian testing main" >> /etc/apt/sources.list
RUN  apt-get autoremove \
  && apt-get -y clean \
  && apt-get -y update \ 
  && apt-get -y upgrade --no-install-recommends \
  && apt-get -y install -o APT::Immediate-Configure=0 apt-transport-https python3 python3-pip python3-boto3 vim sudo python3-jenkins 
RUN pip3 install requests consulate wget

RUN curl https://raw.githubusercontent.com/creationix/nvm/master/install.sh > /tmp/nvm_install.sh; chmod 777 /tmp/nvm_install.sh

COPY --chown=jenkins *.groovy /usr/share/jenkins/ref/init.groovy.d/
COPY --chown=jenkins *.xml /var/jenkins_home/
COPY --chown=root id_rsa /root/.ssh/id_rsa
COPY --chown=root config_xml /var/jenkins_home/config_xml
COPY --chown=jenkins id_rsa /var/jenkins_home/.ssh/id_rsa
COPY --chown=root known_hosts /root/.ssh/known_hosts
COPY --chown=jenkins known_hosts /var/jenkins_home/.ssh/known_hosts
COPY users /var/jenkins_home/users

#RUN wget -nv -O /tmp/ssh-slaves.hpi updates.jenkins-ci.org/download/plugins/ssh-slaves/1.31.5/ssh-slaves.hpi
#RUN wget -nv -O /tmp/ldap.hpi updates.jenkins-ci.org/download/plugins/ldap/2.2/ldap.hpi
#RUN wget -nv -O /tmp/aws-java-sdk.hpi updates.jenkins-ci.org/download/plugins/aws-java-sdk/1.11.930/aws-java-sdk.hpi

RUN cd /tmp; git clone --progress --verbose https://github.com/chuck-hilyard/docker-jenkins-master
RUN chown -R jenkins:jenkins /var/jenkins_home/; chown -R jenkins:jenkins /tmp
RUN echo "jenkins  ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers.d/README

USER jenkins
RUN /tmp/nvm_install.sh
RUN echo "source $HOME/.nvm/nvm.sh" >> /var/jenkins_home/.profile
USER root

COPY init.py /tmp/docker-jenkins-master/init.py
COPY entrypoint.sh /usr/local/bin/
ENTRYPOINT ["entrypoint.sh"]

CMD [ "python3", "-u", "/tmp/docker-jenkins-master/init.py" ]
