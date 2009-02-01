#!/usr/bin/env python
from SocketServer import BaseRequestHandler
from Command import Command
import State as st

class UndefinedInterface(Exception): pass

class DirectConnectInterface (BaseRequestHandler, st.State, Command):
	"""Everything connecting to the DC network should inherit this."""

	def __init__(self, *args):
		SocketServer.BaseRequestHandler.__init__(self, *args)
		st.State.__init__(self)
		Command.__init__(self)

		self.setState(st.CON_STARTED)
		self.__buffer = ''

	def recv(self, command=True, bytes=4096):
		"""Receives and parses the Direct Connect Protocol
		
		Parameters:
			* command - If set to false, everything which follows is 
			            considered data.
			* bytes   - The bytes size limit before writing to buffer"""

		if self.getState in [st.CON_CONNECTED, st.C2H_CONNECTED]:
			msg, self.__buffer = self.__buffer, ''
			chunk = ''

			# Receive until we timeout, get a command or data
			while True and self.getState() > st.CON_QUIT:
				if command and '|' in msg:
					msg, _, self.__buffer = msg.partition('|')
					debug("[IN] %s" % repr(msg)e
					return stripCommand(decode(msg))
				# Get new data
				try:
					chunk = self.request.recv(bytes)
				except socket.timeout:
					pass
				msg += chunk
				# Make sure we've got anything left in the buffer
				# before returning
				if not command and msg != '':
					return msg

			# Need to return something, even after quitting
			return None

	# -------------------- Interfaces  --------------------  #

	def send(self, msg):
		"""Interface must be implemented"""
		raise UndefinedInterface
		
	def quit(self):
		"""Interface must be implemented"""
		raise UndefinedInterface

	def chat(self, msg):
		"""Interface must be implemented"""
		raise UndefinedInterface

	def handle(self): 
		"""Parses data received from the p2p network"""
		raise UndefinedInterface

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

