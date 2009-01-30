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
# ClientToHub 		-	[0-99]
C2H_STARTED			= 	0
C2H_CONNECTED		= 	1
# ClientToClient 	-	[100-199]


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
