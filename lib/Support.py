# Miscellaneous commands related to the Direct Connect Protocol

def encode(text):
  """Removes characters reserved for the DC protocol"""
 
  enc = {
    0   : '/%DCN000%/',
    5  : '/%DCN005%/',
    36  : '/%DCN036%/',
    96  : '/%DCN096%/',
    124  : '/%DCN124%/',
    126  : '/%DCN126%/'
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
	"""Debugging placeholder, to depreciate in favour of the logging module"""
	try:
		if DEBUG: print repr(message)
	except NameError:
		pass
