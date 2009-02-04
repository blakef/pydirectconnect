#!/usr/bin/env python
from Support import getKey, getLock, encode, decode
from Interface import DC_Network, stripCommand
from SocketServer import TCPServer,ThreadingTCPServer
from Client import Client, FILE_TTH, FILE_REGULAR
from Command import Command
from threading import Thread
from time import sleep
import State as st
import socket
import re

DEBUG=False

# ------------------------------------------------------------------------------ #
# H U B
# ------------------------------------------------------------------------------ #
class Hub (DC_Network, Command):
	"""A request handler for Direct Connect client-to-hub communication."""
	def __init__(self, settings):
		"""Opens a connection to the hub"""
		DC_Network.__init__(self)
		Command.__init__(self)

		# Keep track of various information related to the DC Hub
		self.__clients = {}				# List of clients we're connected to
		self.userlist = {}				# List of all clients on the hub
		self.DC_Hub = {}
		self.DC_Settings = settings

		# Add all handlers
		self.addCommand('LOCK', 	self.sendValidation)
		self.addCommand('HUBNAME', 	self.setHubName)
		self.addCommand('HELLO', 	self.authenticate)
		self.addCommand('NICKLIST', self.addUsers)
		self.addCommand('OPLIST', 	self.addUsers)
		self.addCommand('MYINFO', 	self.addUserInfo)
		self.addCommand('QUIT', 	self.removeUser)
		self.addCommand('MSG',		self.showMessage)
		self.addCommand('TO:', 		self.showPrivateMessage)

	def settings(self, settings):
		"""Add all of the server settings.
		
		At a minimum you need a dictionary with:
		 1. 'NICK' 		:	'some nick without spaces'
		 2. 'SHARESIZE'	:	x bytes"""
		self.DC_Settings = settings

	# Duplicated code between Hub and Client, must be a way to join it?
	def handle(self):
		"""Receives commands from the hub, don't call this directly"""
		# Parse the raw data
		while (self.state >= st.CON_STARTED):
			raw = self.recv()
			if raw not in [None, '']:
				self.commandHandler(*raw)
			else:
				sleep(1)
	
	# ------------------Command Handlers ------------------  #

	def showMessage(self, data):
		"""Show us a message"""
		if not DEBUG: print message_decode(data)
	
	def showPrivateMessage(self, data):
		mesg = data.partition('$')
		if mesg[-1] != '':
			src = mesg[0].split()[-1]
			self.showMessage("PRIVATE MESSAGE(%s): %s" % (src,mesg[-1]))
		else:
			debug("Error parsing the message: %s" % data)

	def sendValidation(self, data):
		"""Ask the hub if it likes our Nickname and key"""
		# Get server $lock and $Pk, lock must be the first thing
		# the Direct Connect server sends
		lock,pk = data.split('Pk=')
		self.DC_Hub['LOCK'], self.DC_Hub['PK'] = lock.strip(), pk.strip()
		self.key = getKey(self.DC_Hub['LOCK'])
		# Send $Key
		self.send('$Key %s|' % encode(self.key) + \
		          '$ValidateNick %s|' % self.DC_Settings['NICK'])

	def setHubName(self, data):
		"""Keep a copy of the hubs name"""
		self.DC_Hub['HUBNAME'] = data

	def authenticate(self, data):
		"""Send all of our user information and ask for the nicklist

		* Version: of the DC protocol, default is 1,0091
		* MyINFO:
			Direct Connect Tags (<...>) from http://shakespeer.bzero.se/forum/viewtopic.php?pid=711#p711
			< ClientProgram V:(A),M:(B),H:(C),S:(D)> 
			(A) Version of the ClientProgram
			(B) (P|A), where 'P' is for Passive and 'A' for Active.  I.e. the state of your client
			(C) Describes how many hubs you're of user type: Normal/Registered/Operator, in that order
			(D) Upload Slots
		* LAN(T1): These can be a variety of settings, static for now.
		* Final value: is the share size, we're spoofing this for now."""
		if data.strip() == self.DC_Settings['NICK']:
			self.send("$Version 1,0091|" + \
					  "$GetNickList|" + \
					  "$MyINFO $ALL %s <SuperLeech V:0.1,M:A,H:1/0/0,S:3>" % self.DC_Settings['NICK'] + \
					  "$ " + \
					  "$LAN(T1).$%s@leech.us" % self.DC_Settings['NICK'] + \
					  "$%i$|" % self.DC_Settings['SHARESIZE'])
			self.state = st.C2H_CONNECTED
	
	def removeUser(self, data):
		"""Drops a user from the local list when they sign out"""
		if data.strip() in self.userlist:
			del(self.userlist[data.strip()])

	def addUsers(self, data):
		"""Add preliminary details about a user.
		
		Which is to say: their username"""
		users = data.strip().split('$$')	
		users.remove('')
		getinfo = []
		for user in users:
			if user not in self.userlist:
				getinfo.append(user)
		if getinfo != []:
			msg = ['$GetINFO %s %s|' % (user, self.DC_Settings['NICK']) for user in getinfo]
			self.send(''.join(msg))

	def addUserInfo(self, data):
		"""Get MyINFO from other users.
		
		This has stuff like share size and netspeed.  We don't use much of this
		for now.  More work can be done on extracting this information."""
		data = [x for x in data.split('$') if x not in ['', ' ']]
		if data != []:
			# Note: discarding a lot of the parsed information,
			#       this could be used at a later stage.
			if len(data) == 3:
				data.insert(-1,None)
			info, netspeed, email, sharesize = data
			# Note: We're ignoring anythong that doesn't present
			#       a tag.  Which is to say we're only interested
			#       in users with files.
			#       It's a little messy
			if '<' in info:
				nick, tag = info.split('<')
				nick = nick.lstrip('ALL ').strip()
				nick = re.compile('^\w+').match(nick).group()
				tag = '<'+tag
				sharesize = int(sharesize)
				# Only these for now :)
				self.userlist[nick] = (tag, sharesize)
				# We've got the user list from the server
				self.state = st.C2H_SYNC

	# ------------ Class Specific Methods -----------------  #

	def connect(self, server_address):
		"""Connect to the server, and listens for responses
		
		Be sure to call disconnect so the listening thread dies."""
		self._socket_connect(server_address)
		self._thread = Thread(target=self.handle)
		self._thread.start()

	def disconnect(self):
		if self.state != st.CON_QUIT:
			# Leave the hub
			self.send("$Quit %s|" % self.DC_Settings['NICK'])
			self._socket_disconnect()
			
			# Leave each connected peer
			for client in self.__clients:
				self.__clients[client].quit()
		else:
			debug("Already disconnected from server")

	def chat(self, msg, user=None):
		"""Send the message to a person"""
		message = "<%s>" % self.DC_Settings['NICK'] + \
				  " %s|" % message_encode(msg)

		if user is not None:
			message = "$To: %s " % user + \
					  "From: %s $" % self.DC_Settings['NICK'] + \
					  message
		if user in list(self.userlist) + [None]:
			self.send(message)
		else:
			debug("Unknown user: %s in message:\n%s" % (user, msg))

	def downloadFile(self, client_nick, filename='files.xml.bz2', type=FILE_REGULAR, target='./'):
		"""Creates a TCP server to listen for a p2p connection to upload
		
		A threaded TCP server is created and added to the client list."""
		if self.__clients.get(client_nick) is None:
			settings  = self.DC_Settings
			settings['DOWNLOAD_FILE'] 		= filename
			settings['DOWNLOAD_TYPE'] 		= type
			settings['DOWNLOAD_TARGET'] 	= target
			settings['DOWNLOAD_CLIENT'] 	= client_nick
			client = Client(settings)

			self.__clients[client_nick] = client
			server_thread = Thread(target=self.__clients[client_nick].handle)
			server_thread.start()
			
			# Need to bind to a port before the client can connect
			#while self.__clients[client_nick].state != st.CON_LISTENING:
				#sleep(0.1)

			# Ask hub to connect the clients
			ip, port = self.__clients[client_nick].socket.getsockname()
			self.send("$ConnectToMe %s %s:%i|" % (client_nick, ip, port))
		else:
			debug("Client '%' already has an open connection waiting for it.")
	
	def isClient(self, nick):
		"""Checks if the nick is a current client"""
		return nick in self.__clients
	
	def getClient(self,nick):
		return self.isClient(nick) and self.__clients[nick] or None

# The encoding scheme seems to have changed from /%DCN124%/ -> &#124;
# I've paraphrased the code from DC++: WTF were they thinking?

def message_encode(text):
	"""Removes characters reserved for the DC protocol"""
	for test in ['&#36;','&#124;']:
		text = text.replace(test, '&amp;')

	enc = {
		36	: '&#36;',
		124	: '&#124;',
	}
	swap = lambda x : enc.get(x,chr(x))
	return ''.join([swap(ord(x)) for x in text])

def message_decode(text):
	"""Reverse character encoding for the DC protocol"""
	dec = {
		'&#36;' : '$',
		'&#124;' : '|',
	}
	for test in dec:
		text = text.replace(test, dec[test])
	return text.replace('&amp;','&')

def debug(mesg):
	if DEBUG: print mesg
