#!/usr/bin/env python
import network as DC
import os

def get_ip_address(ifname):
	"""Determines the IP address attached to an ethernet device.
	Taken from: http://code.activestate.com/recipes/439094/"""

	from fcntl import ioctl
	from struct import pack
	from sys import exit
	import socket

	SIOCGIFADDR = 0x8915
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	try:
		return socket.inet_ntoa(ioctl(
			s.fileno(),
			SIOCGIFADDR,
			pack('256s', ifname[:15])
		)[20:24])
	except IOError:
		print "Unable to find network device: %s" % ifname
		#exit(1)
		return None

KILL=False

if __name__ == '__main__':
	if KILL:
		f = open('dc.pid','w')
		f.write(str(os.getpid()))
		f.close()

	settings = {
		'nick'		: 'PyDirectConnect',
		'sharesize'	: 10*1024**3,
		'ip'		: get_ip_address('eth0'),
		'hub'		: ('somehub.com', 411)
	}

	if settings['ip'] is not None:
		hub = DC.DirectConnect(settings)
		hub.connect(*settings['hub'])
		hub.waitUntil(DC.SYNCHRONISED)

		length = max([len(x) for x in hub.userlist])

		for uinfo in hub.userlist.items():
			if uinfo[0] != settings['nick']:
				hub.getFile(uinfo[0], 'files.xml.bz2', target='./')
				print "USER: %s %s" % (uinfo[0].rjust(length), uinfo[1])

		hub.quitHub()
		hub.waitReceiveFiles()

	if KILL:
		os.remove('dc.pid')
