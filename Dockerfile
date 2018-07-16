FROM ubuntu:latest

RUN apt-get update -y && apt-get upgrade -y && apt-get install -y npm wget openjdk-8-jre-headless python3
COPY start_script.txt /etc/init.d/jenkins
RUN ["/bin/bash", "-c", "mkdir -p /rl/{admin,data/logs/nginx,product,sw,logs,shared,local}"]
RUN cd /rl/product; wget http://mirrors.jenkins.io/war-stable/latest/jenkins.war 
RUN chmod +x /etc/init.d/jenkins

#CMD ["/usr/sbin/nginx", "-g", "daemon off;"]
