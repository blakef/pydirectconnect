#!/usr/bin/env python
from Command import Command
from Support import decode
import State as st
import socket

DEBUG=False

class DC_Network:
	"""Wrapper for the socket connection to the hub"""
	def __init__(self):
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.state = st.CON_STARTED
		self.__buffer=''

	def _socket_connect(self, address):
		"""Please don't call these directly"""
		self.socket.connect(address)
		self.state = st.CON_CONNECTED
	
	def _socket_disconnect(self):
		"""Please don't call these directly"""
		self.socket.close()
		self.state = st.CON_QUIT
	
	def recv(self, command=True, bytes=4096):
		"""Receives and parses the Direct Connect Protocol
		
		Parameters:
			* command - If set to false, everything which follows is 
			            considered data.
			* bytes   - The bytes size limit before writing to buffer"""

		if self.state >= st.CON_CONNECTED:
			msg, self.__buffer = self.__buffer, ''
			chunk = ''

			# Receive until we timeout, get a command or data
			while True and self.state > st.CON_QUIT:
				if command and '|' in msg:
					msg, _, self.__buffer = msg.partition('|')
					if msg != '':
						debug("[IN] %s" % repr(msg))
						return stripCommand(decode(msg))
				chunk = self.socket.recv(bytes)
				msg += chunk
				# Make sure we've got anything left in the buffer
				# before returning
				if not command and msg != '':
					return msg

			# Need to return something, even after quitting
			return None

	def send(self, msg):
		self.socket.send(msg)
		debug("[OUT] %s" % repr(msg))
	
	def settimeout(self, seconds):
		"""Causes the socket to timeout after a number of seconds

		If you set this, be sure to wrap any call to 'recv' with 'socket.timeout' exception handling."""
		self.socket.settimeout(seconds)

def stripCommand(string):
	"""Creates a dictionary populate with command.upper -> data"""

	if string != '':
		c,_,d = string.strip().partition(' ')
		if c[0] == '$':
			c = c[1:]
		elif c[0] == '<':
			# Special case, if it's a broadcast message
			c, d = 'MSG', c+' '+d
		string = (c.upper(),d)
	return string

def debug(msg):
	if DEBUG: print msg
