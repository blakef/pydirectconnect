# I'm not blown away with this approach, but I just want a nice way
# to reference a bunch of 'placeholder' constants which make the code
# a little more readable.  At the same time they need to be kept in one
# place in the code, so we don't end up with accidents.
# 
# I see two ways to do this:
# a. A fancy way of generating a list of identifiers with an associated value
# b. Manually adding an identifier and a value.
#
# A the moment I'm siding with (a), since it's cleaner IMHO.  The code for (b) 
# is included, but I'd discourage using this approach
#

# Option A:
# Fatal Exceptions	-	[ <0 ]
CON_ERROR_FATAL		=	-2
CON_QUIT			=	-1
# Generic states	-	[0-99]
CON_GENERIC			=	0
CON_STARTED			=	1
CON_LISTENING		=	2
CON_CONNECTED		=	3
CON_DATA_MODE		=	4
# ClientToHub 		-	[100-199]
C2H_GENERIC			=	100
C2H_STARTED			= 	101
C2H_CONNECTED		= 	102
C2H_SYNC			=	103
# ClientToClient 	-	[200-299]
C2C_GENERIC			=	200
C2C_CONNECTED		=	201
C2C_DOWNLOAD_READY	=	202
C2C_DOWNLOAD_DONE	=	203


# Option B:
#class Const(dict):
#	const = [
#		'OFFLINE',
#		'ONLINE',
#		'',
#	]
#	def __init__(self):
#		# Unique and relevant idenitifers only; set all to uppercase
#		const = [str(k).upper() for k in {}.fromkeys(self.const).keys() if k != '']
#
#		for count, ident in enumerate(const):
#			setattr(self, ident, count)
#			self.__setitem__(ident, count)

class State:
	def __init__(self):
		self.__state == None

	def setState(self, state):
		"""Changes the state to something defined in states.py
		
		This should only be used internally.  May look at checking transitions
		from one state to another to indicate errors, or trigger events?"""

		self.__state = state
	
	def getState(self): return self.__state

