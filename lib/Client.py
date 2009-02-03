#!/usr/bin/env python
from Interface import DirectConnectInterface
from zlib import decompressobj
from time import sleep
import State as st
import os

FILE_REGULAR	= 0xCAFE
FILE_TTH		= 0xBABE

class Client (DirectConnectInterface):
	"""A request handler for direct connect client-to-client communication."""

	def __init__(self, *args):
		"""Opens a p2p connection to another client."""
		DirectConnectInterface.__init__(self, *args)	

		# Add command handlers
		self.addCommand('MYNICK',		self.setNick)
		self.addCommand('LOCK', 		self.setLock)
		self.addCommand('SUPPORTS', 	self.setSupports)
		self.addCommand('DIRECTION', 	self.setDirection)
		self.addCommand('ADCSND', 		self.readyFile)
		self.addCommand('KEY', 			self.readyDownload)
		self.addCommand('ERROR', 		self.error)

	# -------------------- Interfaces  --------------------  #

	def send(self, msg):
		self.request.send(msg)

	def quit(self):
		# Do we need to send the client something, check state maybe?
		self.shutdown()

	# ------------ Class Specific Methods -----------------  #

	def setNick(self, data):
		self.client = data.strip()

	def setLock(self, data):
		lock,pk = data.split('Pk=')
		self.lock, self.pk = lock.strip(), pk.strip()

		# Once we have the lock, we need to update sync with the client
		# NOTE: We're lying about what we support at the moment.  The direction
		#       should also generate a random number, I want always download
		#       first.  This 'breaks' protocol.
		self.send("$MyNick %s|" % self.conn.nick + \
				  "$Lock %s Pk=%s|" % (self.lock, self.pk) + \
				  "$Supports MiniSlots XmlBZList ADCGet TTHL TTHF |" + \
				  "$Direction Download 65535|" + \
				  "$Key %s|" % getKey(self.lock))
	
	def setSupports(self, data):
		self.supports = data.split()
	
	def setDirection(self, data):
		"""Checks the the client will send upload to us"""
		direction, val = data.split()
		if direction.upper() != 'UPLOAD':
			self.state = st.CON_ERROR_FATAL
	
	def readyDownload(self):
		"""$Key received, the client is ready to send"""
		self.state = st.C2C_DOWNLOAD_READY

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
				chunk = self.recv(False,chunk_bytes)
				if self.file_mode == FILE_TTH:
					chunk = self.zstream.decompress(chunk)
				file_total -= len(chunk)
				f.write(chunk)
		finally:
			f.close()
		#print "Done"

		# Close the connection to the client
		self.state = self.C2C_DOWNLOAD_DONE
		self.quit()
