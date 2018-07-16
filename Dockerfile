FROM ubuntu:latest

RUN apt-get update -y && apt-get upgrade -y && apt-get install -y npm wget openjdk-8-jre-headless openjdk-8-jdk-headless python3 git vim
COPY start_stop_jenkins.txt /etc/init.d/jenkins
RUN cd /tmp; git clone https://github.com/chuck-hilyard/docker-jenkins; cd docker-jenkins; git pull
RUN ["/bin/bash", "-c", "mkdir -p /rl/{admin,data/logs/nginx,product,sw,logs,shared,local}"]
RUN cd /rl/product; wget http://mirrors.jenkins.io/war-stable/latest/jenkins.war 
RUN chmod +x /etc/init.d/jenkins

CMD ["java", "-jar", "/rl/product/jenkins.war"]
