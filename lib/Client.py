#!/usr/bin/env python
from Interface import DC_Network
from Command import Command
from Support import getKey
from zlib import decompressobj
from time import sleep
import State as st
import socket
import os

FILE_REGULAR	= 0xCAFE
FILE_TTH		= 0xBABE

DEBUG=False

class DC_Client_Network(DC_Network):
	def _socket_bind(self, address):
		self.socket.bind(address)
		self.socket.listen(1)
		self.state = st.CON_LISTENING

	def _socket_listen(self, timeout=10):
		self.socket.settimeout(timeout)
		address = None
		try:
			conn, address = self.socket.accept()
			self.socket.close()
			self.socket = conn
		except socket.timeout:	
			self.state = st.CON_QUIT
		else:
			self.state = st.CON_CONNECTED
		return address
	
class Client (DC_Client_Network, Command):
	"""A request handler for direct connect client-to-client communication."""

	def __init__(self, settings):
		"""Opens a p2p connection to another client."""
		DC_Client_Network.__init__(self)	
		Command.__init__(self)
		# Add command handlers
		self.addCommand('MYNICK',		self.setNick)
		self.addCommand('LOCK', 		self.setLock)
		self.addCommand('SUPPORTS', 	self.setSupports)
		self.addCommand('DIRECTION', 	self.setDirection)
		self.addCommand('ADCSND', 		self.readyFile)
		self.addCommand('KEY', 			self.readyDownload)
		self.addCommand('ERROR', 		self.error)

		self.DC_Settings = settings
		self._socket_bind( (settings['ADDRESS'], 0) )

	# -------------------- Interfaces  --------------------  #

	def quit(self):
		self._socket_disconnect()
	
	# Duplicated code between Hub and Client, must be a way to join it?
	def handle(self):
		"""Handles incoming command parsing
		
		This only requires the (Base|TCP|ThreadedTCP)Server.handle_request() be called.  Don't
		call handle_forever()."""
		# Wait until the client has connected
		user_connected = self._socket_listen()
		debug("USER: %s connected" % repr(user_connected))

		while (self.state >= st.CON_STARTED):
			try:
				raw = self.recv()
			except socket.timeout:
				self.quit()

			if raw not in [None, '']:
				self.commandHandler(*raw)
			else:
				sleep(1)

	# ------------ Class Specific Methods -----------------  #

	def setNick(self, data):
		self.client = data.strip()

	def setLock(self, data):
		lock,pk = data.split('Pk=')
		self.DC_Settings['LOCK'], self.DC_Settings['PK'] = lock.strip(), pk.strip()

		# Once we have the lock, we need to update sync with the client
		# NOTE: We're lying about what we support at the moment.  The direction
		#       should also generate a random number, I want always download
		#       first.  This 'breaks' protocol.
		self.send("$MyNick %s|" % self.DC_Settings['NICK'] + \
				  "$Lock %s Pk=%s|" % (self.DC_Settings['LOCK'], self.DC_Settings['PK']) + \
				  "$Supports MiniSlots XmlBZList ADCGet TTHL TTHF |" + \
				  "$Direction Download 65535|" + \
				  "$Key %s|" % getKey(self.DC_Settings['LOCK']))
	
	def setSupports(self, data):
		self.supports = data.split()
	
	def setDirection(self, data):
		"""Checks the the client will send upload to us"""
		direction, val = data.split()
		if direction.upper() != 'UPLOAD':
			self.state = st.CON_ERROR_FATAL
	
	def readyDownload(self, data):
		"""$Key received, the client is ready to send"""
		self.state = st.C2C_DOWNLOAD_READY
		self.getFile(self.DC_Settings['DOWNLOAD_FILE'], \
		             self.DC_Settings['DOWNLOAD_TYPE'], \
		             self.DC_Settings['DOWNLOAD_TARGET'])
	
	def error(self, data):
		debug("Unknown message: %s" % repr(data))

	def getFile(self, filename, type=FILE_REGULAR, target='./', timeout=10):
		self.file_mode = type
		self.file_path = target
		while self.state != st.C2C_DOWNLOAD_READY and timeout > 0:
			sleep(1)
			timeout -= 1
		if self.state == st.C2C_DOWNLOAD_READY:
			msg = {
				FILE_REGULAR : "$ADCGET file %s 0 -1|",
				FILE_TTH     : "$ADCGET file TTH/%s 0 -1 ZL1|"
			}
			self.send(msg[type] % filename)
	
	def readyFile(self, data, buff_max=10*1024**2):
		data = data.split()
		if self.file_mode == FILE_TTH:
			print "TTH MODE"
			self.zstream = decompressobj()
			data = data[:-1]
		file_type,file_ident,start,bytes = data
		filename = os.path.join(self.DC_Settings['DOWNLOAD_TARGET'], \
		                        self.DC_Settings['DOWNLOAD_CLIENT'] + \
								'-' + \
								os.path.split(file_ident)[1])
		f = open(filename, 'wb')
		file_total = int(bytes)
		chunk_bytes = 4096
		chunk = None

		write_error = False
		try:
			debug('%s - Filelist Started' % self.DC_Settings['DOWNLOAD_CLIENT'])
			while file_total > 0:
				if file_total < chunk_bytes:
					chunk_bytes = file_total

				try:
					chunk = self.recv(False,chunk_bytes)
				except socket.timeout:
					complete = (1-file_total/float(bytes))*100
					debug('%s' % self.DC_Settings['DOWNLOAD_CLIENT'] + \
					      '- Filelist Downloaded interrupted at %.2f%%' % complete)
					write_error = True
					break	

				if self.file_mode == FILE_TTH:
					chunk = self.zstream.decompress(chunk)
				if chunk is not None:
					file_total -= len(chunk)
					f.write(chunk)
		finally:
			f.close()
			debug('%s - Filelist Downloaded' % self.DC_Settings['DOWNLOAD_CLIENT'])

		if write_error:
			os.remove(f.name)	
		# Close the connection to the client
		self.state = st.C2C_DOWNLOAD_DONE
		self.quit()

def debug(msg):
	if DEBUG: print msg
