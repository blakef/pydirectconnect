#!/usr/bin/env python
import states as st

class UndefinedInterface(Exception): pass

class DirectConnectInterface (SocketServer.BaseRequestHandler):
	"""Everything connecting to the DC network should inherit this."""

	def __init__(self):
		self.__setState(st.C2H_STARTED)

	# BaseRequestHandler
	def handle(self): 
		"""Parses data received from the p2p network"""
		pass

	# Private
	def __setState(self, state):
		"""Changes the state to something defined in states.py
		
		This should only be used internally.  May look at checking transitions
		from one state to another to indicate errors, or trigger events?"""
		self.__state = state

	def __commandHandler(self):
		"""Calls a function based on a command received from the hub.
		
		Once command are added using 'addCommand', this will lookup the command
		received through 'handle'.  Implementors shouldn't have to know about this."""	
		pass

	# Public
	def addCommand(self, ident, func):
		"""Specify a function to be called on a command being received.

		All functions should accept one paramter, with the comman payload.  For example suppose
		the hub sends out client '$Hello Foobar|'.  This will be unwrapped, and a command added
		as:

			bob.addCommand('HELLO', somehandlerfunction)

		Will then be called with:

			somehandlerfunction('Foobar')
		""" 
		pass

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

class Hub (DirectConnectInterface):
	def __init__(self, hub_addr):
		"""Opens a connection to the hub"""
		self.__clients = []

		DirectConnectInterface.__init__(self)	

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

class Client (DirectConnectInterface):
	def __init__(self, hub_addr):
		"""Opens a p2p connection to another client."""
		
		# Add command handlers
		#self.addHandler('HELLO', self.foobar)

		DirectConnectInterface.__init__(self)	
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


# ------------ OLD CODE BELOW, BRING TRACTORS ---------------------------------------- #
import re
import os
import socket
import random
import threading
from sys import exit
from time import sleep
from zlib import decompressobj

# Possible states for a Direct Connect Client
[OFFLINE, CONNECTED, AUTHENTICATED, LISTENING, SYNCHRONISED, ABORT, QUIT] = range(7)
# Types of downloads
[FILE_REGULAR, FILE_TTH] = range(2)


class Network:
	"""A Direct Connect Client's network operations"""
	def __init__(self, ip):
		self.ip = ip 
		self.state = OFFLINE
		self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		self.buffer = ''
	
	def send(self, msg):
		if self.state in [CONNECTED, AUTHENTICATED, SYNCHRONISED]:
			self.socket.sendall(msg)
			debug("[OUT] %s" % repr(msg))
	
	def recv(self, command=True, bytes=4096):
		if self.state in [CONNECTED, AUTHENTICATED, SYNCHRONISED]:
			msg, self.buffer = self.buffer, ''
			chunk = ''

			# Receive until we timeout, get a command or data
			while True and self.state != QUIT:
				if command and '|' in msg:
					msg, _, self.buffer = msg.partition('|')
					debug("[IN] %s" % repr(msg))
					return stripCommand(decode(msg))
				# Get new data
				try:
					chunk = self.socket.recv(bytes)
				except socket.timeout:
					pass
				msg += chunk
				# Make sure we've got anything left in the buffer
				# before returning
				if not command and msg != '':
					return msg

			# Need to return something, even after quitting
			return ('','')
	
	def quit(self):
		self.state = QUIT
		self.socket.close()


class DirectConnectClient(Network):
	def __init__(self, ip):
		Network.__init__(self, ip)
		self.socket.settimeout(CLIENT_TIMEOUT)

	def connect(self, server, port):
		"""Connects to a server"""
		assert type(server) is str and type(port) is int
		try:
			self.socket.connect((server, port))
			self.state = CONNECTED
		except socket.error, e:
			self.state = ABORT
			print e


class DirectConnectServer(Network):
	def __init__(self, ip, nick):
		Network.__init__(self, ip)
		self.socket.bind((self.ip, 0))
		self.socket.listen(1)
		# Thread watching
		self.lock = threading.Lock()
		self.serversRunning = 0
		self.socket.settimeout(SERVER_TIMEOUT)
		
		self.nick = nick
	
	def listen(self, client_nick):
		"""Listens for a client to connect"""
		self.client = Server(client_nick, self)
		self.client.start()
		self.server_count(1)
		return self.socket.getsockname()

	def server_count(self, amount):
		"""Adjust the number of servers, typically passing 1 or -1 to amount."""
		self.lock.acquire()
		self.serversRunning += amount
		self.lock.release()
	
	def newConnection(self, socket):
		self.socket = socket
		self.socket.settimeout(SERVER_TIMEOUT)

# ------------------------------------------------------------------------------------------ #

class Server(threading.Thread):

	[SERVER_INIT, SERVER_READY, SERVER_DOWNLOADED] = range(3)

	def __init__(self, client_nick, conn):
		self.conn = conn
		self.client_nick = client_nick
		self.client = self.state = self.file = None
		threading.Thread.__init__(self)
		self.setName("Thread: %s " % client_nick)
	
	def run(self):
		# Setup the connection with the client
		# and swap the sockets
		try:
			client_socket, client_addr = self.conn.socket.accept()	
			self.conn.newConnection(client_socket)
			self.conn.state = CONNECTED
		except socket.timeout:
				# If the client doesn't immediately connect, quit
				self.conn.state = QUIT
			# Initiate Protocol Exchange
		reactor = {
			'MYNICK' 	: lambda x : self.setNick(x),
			'LOCK'		: lambda x : self.setLock(x),
			'SUPPORTS'	: lambda x : self.setSupports(x),
			'DIRECTION'	: lambda x : self.setDirection(x),
			'ADCSND'	: lambda x : self.readyFile(x),
			'KEY'		: lambda x : self.readyDownload(),
			'ERROR'		: lambda x : self.error(x)
		}
		self.state = self.SERVER_INIT
		while self.conn.state != QUIT:
			try:
				# Being called after I've got data from my client
				raw = self.conn.recv()
				if raw != None:
					cmd, data = raw
					reactor.get(cmd, lambda x : 'Ignored: %s' % x)(data)
				else:
					sleep(5)
			except ValueError, e:
				# Case: Incorrectly packaged commands:  |$Command ||$Command
				#       We ignore these.
				pass

		# Closing the server, inform the count
		self.conn.server_count(-1)
	
	def error(self, data):
		print "Error: %s" % data
		self.conn.state = QUIT

	def setNick(self, data):
		self.client = data.strip()

	def setLock(self, data):
		lock,pk = data.split('Pk=')
		self.lock, self.pk = lock.strip(), pk.strip()

		# Once we have the lock, we need to update sync with the client
		# NOTE: We're lying about what we support at the moment.  The direction
		#       should also generate a random number, I want always download
		#       first.  This 'breaks' protocol.
		# XXX: Replace dummy value for the key in the future
		self.conn.send("$MyNick %s|" % self.conn.nick + \
			       "$Lock %s Pk=%s|" % (self.lock, self.pk) + \
			       "$Supports MiniSlots XmlBZList ADCGet TTHL TTHF |" + \
			       "$Direction Download 65535|" + \
			       "$Key %s|" % getKey(self.lock))
	
	def setSupports(self, data):
		self.supports = data.split()
	
	def setDirection(self, data):
		direction, val = data.split()
		if direction.upper() == 'UPLOAD':
			self.state = self.SERVER_READY
	
	def readyDownload(self):
		# $Key received, the client is ready to send
		self.state = self.SERVER_READY

	def getFile(self, filename, type=FILE_REGULAR, target='./', timeout=10):
		self.file_mode = type
		self.file_path = target
		while self.state != self.SERVER_READY and timeout > 0:
			sleep(1)
			timeout -= 1
		if self.state == self.SERVER_READY:
			msg = {
				FILE_REGULAR : "$ADCGET file %s 0 -1|",
				FILE_TTH     : "$ADCGET file TTH/%s 0 -1 ZL1|"
			}
			self.conn.send(msg[type] % filename)
	
	def readyFile(self, data, buff_max=10*1024**2):
		data = data.split()
		if self.file_mode == FILE_TTH:
			print "TTH MODE"
			self.zstream = decompressobj()
			data = data[:-1]
		file_type,file_ident,start,bytes = data
		filename = os.path.join(self.file_path, \
		                        self.client + '-' + os.path.split(file_ident)[1])
		f = open(filename, 'wb')
		file_total = int(bytes)
		chunk_bytes = 4096
		chunk = None

		try:
			while file_total > 0:
				if file_total < chunk_bytes:
					chunk_bytes = file_total
				chunk = self.conn.recv(False,chunk_bytes)
				if self.file_mode == FILE_TTH:
					chunk = self.zstream.decompress(chunk)
				file_total -= len(chunk)
				f.write(chunk)
		finally:
			f.close()
		#print "Done"

		# Close the connection to the client
		self.state = self.SERVER_DOWNLOADED
		self.conn.quit()
			
class DirectConnect(object):
	"""Client <-> Hub communication"""

	def __init__(self, settings):
		self.nw = DirectConnectClient(settings['ip'])
		self.ip = settings['ip']
		self.dcServer = {}
		self.nick = settings['nick']
		self.shareSize = settings['sharesize']
		self.userlist = {}

	def connect(self, server):
		self.nw.connect(*server)
		# Startup background command processing
		self.background = Core(self)
		self.background.start()
	
	def waitUntil(self, state, timeout=5):
		"""Delay until the connection to the hub is in a state:
		
		* OFFLINE		- DirectConnect object instantiated, but not connected	
		* CONNECTED		- Client is connected to the hub
		* AUTHENTICATED - Hub digs us and we're allowed to send stuff to everyone
		* LISTENING		- [Depreciated]
		* SYNCHRONISED	- The list of users on a hub has been sent
		* ABORT			- Connection to the hub failed
		* QUIT			- Hub session is closed"""

		while self.nw.state != state:
			sleep(1)
	
	def waitFileDownload(self):
		"""[Depreciated] Waits until all running connections have been closed"""
		try:
			while self.servers.serversRunning != 0:
				sleep(1)
		except AttributeError:
			pass
	
	def waitReceiveFiles(self):
		"""Will wait until all P2P connections have closed"""

		for t in reversed(threading.enumerate()[1:]):
			debug("Waiting: %s" % t.getName())
			t.join()
	
	def getFile(self, user, file, type=FILE_REGULAR, target='./'):
		"""Requests a file from a user connected to the hub
		
		The listening server is assigned to an attribute 'server'.  This
		server is threaded."""

		self.server = DirectConnectServer(self.ip, self.nick)
		ip, port = self.server.listen(user)
		self.nw.send('$ConnectToMe %s %s:%i|' % (user, ip, port))

		# Write file lists to a directory
		self.server.client.getFile(file, type, target)
	
	def quitHub(self):
		"""Tell the hub we're outta here
		
		Kills the network connection after following DC protocol."""
		self.nw.send('$Quit %s|' % self.nick)
		self.nw.quit()
		# XXX: Find out why the threads aren't quitting!
		#exit(0)
		
class Core(threading.Thread):
	"""The DirectConnect Hub <-> Local Client protocol."""

	def __init__(self, directconnect) :
		self.dc = directconnect
		threading.Thread.__init__(self)

	def run(self):
		reactor = {
			'LOCK' 		: lambda x : self.startConnection(x),
			'HUBNAME' 	: lambda x : self.setHubName(x),
			'HELLO'		: lambda x : self.authenticate(x),
			'NICKLIST' 	: lambda x : self.addUsers(x),
			'OPLIST' 	: lambda x : self.addUsers(x),
			'MYINFO' 	: lambda x : self.addUserInfo(x),
			'QUIT'		: lambda x : self.removeUser(x)
		}

		while self.dc.nw.state != QUIT:
			# Note: As long as the socket timeout is set to something
			#       reasonable (>=2 seconds), this approach should be
			#       find.  If sockets.recv is set to block it'll break
			#       or if the timeout is unreasonably low it'll kill the
			#       cpu.  You've been warned!
			try:
				cmd, data = self.dc.nw.recv()
				reactor.get(cmd, lambda x : 'Ignored: %s' % x)(data)
			except ValueError:
				# Case: Incorrectly packaged commands:  |$Command ||$Command
				#       We ignore these.
				pass

	
	def startConnection(self, data):
		"""Ask the hub if it likes our Nickname and key"""

		# Get server $lock and $Pk, lock must be the first thing
		# the Direct Connect server sends
		lock,pk = data.split('Pk=')
		self.dc.dcServer['LOCK'], self.dc.dcServer['PK'] = lock.strip(), pk.strip()
		self.dc.key = getKey(self.dc.dcServer['LOCK'])
		
		# Send $Key
		self.dc.nw.send('$Key %s|' % encode(self.dc.key) + \
		                '$ValidateNick %s|' % self.dc.nick)


	def setHubName(self, name):
		"""Keep a copy of the hubs name"""

		self.setName(name)
		self.dc.dcServer['HUBNAME'] = name

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
		if data.strip() == self.dc.nick:
			self.dc.nw.send("$Version 1,0091|" + \
							"$GetNickList|" + \
							"$MyINFO $ALL %s <SuperLeech V:0.1,M:A,H:1/0/0,S:3>" % self.dc.nick + \
							"$ " + \
							"$LAN(T1).$%s@leech.us" % self.dc.nick + \
							"$%i$|" % self.dc.shareSize)
			self.dc.nw.state = AUTHENTICATED
	
	def removeUser(self, data):
		"""Drops a user from the local list when they sign out"""

		if data.strip() in self.dc.userlist:
			del(self.dc.userlist[data.strip()])

	def addUsers(self, data):
		"""Add preliminary details about a user.
		
		Which is to say: their username"""

		users = data.strip().split('$$')	
		users.remove('')
		getinfo = []
		for user in users:
			if user not in self.dc.userlist:
				getinfo.append(user)
		if getinfo != []:
			msg = ['$GetINFO %s %s|' % (user, self.dc.nick) for user in getinfo]
			self.dc.nw.send(''.join(msg))

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
				self.dc.userlist[nick] = (tag, sharesize)
				# We've got the user list from the server
				self.dc.nw.state = SYNCHRONISED

def stripCommand(string):
	"""Creates a dictionary populate with command.upper -> data"""

	if string != '':
		c,_,d = string.strip().partition(' ')
		if c[0] == '$':
			c = c[1:]
		string = (c.upper(),d)
	return string



# ------------------------------------------------------------------------------------------ #

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

# ------------------------------------------------------------------------------------------ #

CLIENT_TIMEOUT = 2.0		# XXX: Required, build it into the classes
SERVER_TIMEOUT = 5.0		# XXX: Required, build it into the classes
DEBUG=False
