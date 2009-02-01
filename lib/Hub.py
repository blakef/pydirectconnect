#!/usr/bin/env python
from Interface import DirectConnectInterface
from SocketServer import TCPServer,ThreadedTCPServer
from threading import Thread
import State as st
import socket
import re

DEBUG=False

class ConfigurationError(Exception): pass

class DirectConnectServer(TCPServer):
	"""We're going hjack the features of a TCPServer, but initiate the connection."""
	def __init__(self, server_address, RequestHandlerClass):
		TCPServer.__init__(self, server_address, RequestHandlerClass)
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	
	def get_request(self):
		return (self.socket.connect(self.server_address), self.server_address)

	def server_bind(self): pass
	def server_activate(self): pass

class Hub (DirectConnectInterface):
	"""A request handler for Direct Connect client-to-hub communication."""

	def __init__(self, *args):
		"""Opens a connection to the hub"""
		DirectConnectInterface.__init__(self, *args)
		self.__clients = {}				# List of clients we're connected to
		self.userlist = {}				# List of all clients on the hub
		self.DC_Hub = {}
		self.DC_Settings = None
	
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

	def connect(self, settings):
		"""Requires a complete list of settings in a dictionary:
		
		Must include:
		 * 'ADDRESS'	:	(ip_address, port)
		 * 'NICK'		:	'SomeName, no spaces please'"""

		self.DC_Settings = settings
		# Little fu, :)
		self.server_close()
		self.socket

    def handle(self):
		"""Receives commands from the hub"""
		# Parse the raw data
		while (self.getState() >= CON_STARTED):
			raw = self.recv()
			if raw is not None: self.commandHandler(*raw)

	# ------------------Command Handlers ------------------  #

	def showMessage(self, data):
		"""Show us a message"""
		print decode(data)
	
	def privateMessage(self, data):
		mesg = data.partition('$')
		if mesg[-1] != '':
			self.showMessage(mesg[-1])
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
		          '$ValidateNick %s|' % self.nick)

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

		if data.strip() == self.nick:
			self.send("$Version 1,0091|" + \
					  "$GetNickList|" + \
					  "$MyINFO $ALL %s <SuperLeech V:0.1,M:A,H:1/0/0,S:3>" % self.nick + \
					  "$ " + \
					  "$LAN(T1).$%s@leech.us" % self.nick + \
					  "$%i$|" % self.shareSize)
			self.setState(st.C2H_CONNECTED)
	
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
			msg = ['$GetINFO %s %s|' % (user, self.dc.nick) for user in getinfo]
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
				self.setState(st.C2H_SYNC)

	# -------------------- Interfaces  --------------------  #

	def send(self, msg):
		"""Interface must be implemented"""
		self.request.send(msg)
		
	def quit(self):
		"""Interface must be implemented"""
		self.send("$Quit %s|" % self.DC_Settings['NICK'])
		self.setState(st.CON_QUIT)

	# ------------ Class Specific Methods -----------------  #

	def chat(self, msg, user=None):
		"""Send the message to a person"""
		message = "<%s>" % self.DC_Settings['NICK'] + \
				  " %s|" % encode(msg)

		if user is not None:
			message = "$To: %s " % user + \
					  "From: %s$" % self.DC_Settings['NICK'] + \
					  message
		if isClient(user):
			self.request.send(encode(message))
		else:
			debug("Unknown user: %s" % user)

	def addClient(self, client_nick):
		"""Creates a TCP server to listen for a p2p connection.
		
		A threaded TCP server is created and added to the client list."""

		if self.__clients.get(client_nick) is None:
			self.__clients[client_nick] = \
				SocketServer.ThreadedTCPServer((self.hub_addr, 0), Client(client_nick))
			server_thread = Thread(target=self.__clients[client_nick].serve_forever)
			# XXX: Need to investigate the difference here:
			#server_thread.setDaemon(True)
			server_thread.start()
			# Ask hub to connect the clients
			ip, port = self.__clients[client_nick].server_address
			self.send("$ConnectToMe %s %s:%i|" % (client_nick, ip, port))
		else:
			debug("Client '%' already has an open connection waiting for it.")
	
	def isClient(self, nick):
		"""Checks if the nick is a current client"""
		return nick in self.__clients

# ---------------------------------------------------------------
# Miscellaneous commands:
# ---------------------------------------------------------------

def encode(text):
	"""Removes characters reserved for the DC protocol"""

	enc = {
		0 	: '/%DCN000%/',
		5	: '/%DCN005%/',
		36	: '/%DCN036%/',
		96	: '/%DCN096%/',
		124	: '/%DCN124%/',
		126	: '/%DCN126%/'
	}
	swap = lambda x : enc.get(x,chr(x))
	return ''.join([swap(ord(x)) for x in text])

def decode(text):
	"""Reverse character encoding for the DC protocol"""

	dec = {
		'/%DCN000%/' : '\x00',
		'/%DCN005%/' : '\x05',
		'/%DCN036%/' : '\x1a',
		'/%DCN096%/' : '`',
		'/%DCN124%/' : '|',
		'/%DCN126%/' : '~'
	}
	for test in dec:
		text = text.replace(test, dec[test])
	return text	

def getLock(length=80):
	"""Creates a random lock

	A couple of useful lenghts for various keys:
		* Lock:	80 - 134 chars
		* Pk:	16 chars"""

	return encode(''.join([chr(random.randrange(33,127)) for x in range(length)]))

def getKey(lock):
	"""Creates a key from a supplied lock, don't forget to encode"""

	lock = [ord(x) for x in lock]
	key = []
	for x in range(1,len(lock)):
		key.append(lock[x-1] ^ lock[x])
	key = [lock[0] ^ lock[-1] ^ lock[-2] ^ 5] + key
	nibbleswap = lambda x : ((x << 4) & 240) | ((x >> 4 & 15))
	return ''.join([chr(nibbleswap(x)) for x in key])

def debug(message):
	if DEBUG: print message
