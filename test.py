#!/usr/bin/env python3

consul = consulate.Consul()

# Get all of the service checks for the local agent
checks = consul.agent.checks()

# Get all of the services registered with the local agent
services = consul.agent.services()

# Add a service to the local agent
consul.agent.service.register('redis',
                               port=6379,
                               tags=['master'],
                               ttl='10s')
