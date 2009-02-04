#!/usr/bin/env python
from Support import debug

class Command:
	def __init__(self):
		self.__commands = {}

	def commandHandler(self, command, data):
		"""Calls a function based on a command received from the hub.
		
		Once command are added using 'addCommand', this will lookup the command
		received through 'handle'.  Implementors shouldn't have to know about this."""	

		react = self.__commands.get(str(command).upper())
		if react is not None:
			react(data)
		else:
			debug("Unknown command: %s" % repr( (command, data) ))

	def addCommand(self, ident, func):
		"""Specify a function to be called on a command being received.

		All functions should accept one paramter, with the comman payload.  For example suppose
		the hub sends out client '$Hello Foobar|'.  This will be unwrapped, and a command added
		as:

			bob.addCommand('HELLO', somehandlerfunction)

		Will then be called with:

			somehandlerfunction('Foobar')""" 
		self.__commands[str(ident).upper()] = func

