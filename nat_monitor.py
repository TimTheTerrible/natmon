#!/usr/bin/python -u

import os
import sys
import time
import boto.vpc

from nat_config import *

# Timing values
WaitBetweenChecks = 3
WaitForStop = 15
WaitForStart = 30
WaitForBoot = 120

# Utility functions

def check_host_reachable ( hostIP ):
	return (os.system("ping -c 3 -w 5 %s 2>&1 > /dev/null" % hostIP) == 0)

def get_instance ( instanceID ):
	return vpc.get_all_instances([instanceID])[0].instances[0]

def restart_instance ( instance ):
	print "Stopping instance %s..." % instance.id
	instance.stop()
	while ( instance.state != "stopped" ):
		print "Waiting for instance %s to stop..." % instance.id
		time.sleep(WaitForStop)
		instance.update()
		print "Instance %s is %s" %(instance.id,instance.state)

	print "Starting instance %s..." % instance.id
	instance.start()
	while ( instance.state != "running" ):
		print "Waiting for instance %s to start..." % instance.id
		time.sleep(WaitForStart)
		instance.update()
		print "Instance %s is %s" %(instance.id,instance.state)

def assume_primary_role ():
	# Make sure I have the route and elasticIP

	# In order to prevent the NAT from emitting packets from its
	# auto-assigned Public IP, move the Elastic IP first,
	# then move the route.

	# Get the address object for the egress IP...
	address = vpc.get_all_addresses(addresses=egress_ip)[0]
	# Check to see if it's associated...
	association_id = address.association_id
	# If so, disassociate it...
	if ( association_id != None ):
		vpc.disassociate_address(association_id=association_id)
	# Now, associate it with this NAT...
	vpc.associate_address(instance_id=this_nat.id,allocation_id=address.allocation_id)
	# Replace the default route destination with me...
	vpc.replace_route(route_table_id=our_nat_rt,destination_cidr_block="0.0.0.0/0",instance_id=this_nat.id)

# Startup

try:
	# Connect to EC2...
	print "Connecting to EC2 (%s)" % region
	vpc = boto.vpc.connect_to_region(region)

	# Get info about this NAT...
	this_nat = get_instance(this_nat_id)
	print "This nat: %s (%s)" % (this_nat.tags["Name"],this_nat.private_ip_address)

	# Get info about the other NAT...
	other_nat = get_instance(other_nat_id)
	print "Other nat: %s (%s)" % (other_nat.tags["Name"],other_nat.private_ip_address)

except Exception, e:
	print "EC2 data gathering failed: %s" % e
	sys.exit(1)

if ( role == ROLE_PRIMARY ):
	print "Role: I'm the primary NAT"
	assume_primary_role()
else:
	print "Role: I'm the secondary NAT"
	# do nothing

# Main Program

print "Starting NAT monitor"

while True:

	#print "Checking other nat..."

	if ( check_host_reachable(other_nat.private_ip_address) ):
		#print "Other NAT is OK; sleeping..."
		time.sleep(WaitBetweenChecks)
	else:
		print "Other NAT is down!"

		if ( role == ROLE_SECONDARY ):
			assume_primary_role()

		# Restart the other NAT...
		print "Restarting the other NAT..."
		restart_instance(other_nat)
		time.sleep(WaitForBoot)

