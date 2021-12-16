import aiohttp
import random
import asyncio
from urllib.parse import urlencode
from bencoding import decode



class Tracker:
  '''
  Established Connection with a Tracker for a given Torrent.
  The tracker is an HTTP(S) service that holds information about the torrent and peers.
  The tracker itself does not have the file you want to download,
  but it does have a list of all peers that are connected for this torrent who have the file or are downloading the file.
  It responds to GET requests with a list of peers.
  '''

  def __init__(self, torrent):
    self.torrent = torrent
    self.peer_id = self.calculate_peer_id()
    self.http_client = aiohttp.ClientSession()

  def connect(self, first: bool=None, uploaded: int=0, downloaded: int=0):
    '''
    Makes the 'announce' call to the tracker URL optained from the info['announce'] that we parsed from the .torrent file.
    If the call with successful, the tracker returns a response, of interest to us is the peer list which is a list of peers
    that currently have the file and are ready to seed it.

    :param first : whether or not this is our first contact with this particular tracker.
    :param uploaded : The total number of bytes uploaded.
    :param downloaded : The total number of bytes downloaded.
    
    The parameters required in the tracker get request:

    info_hash:   The SHA1 hash of the info dict found in the .torrent
    peer_id:	   A unique ID generated for this client
    uploaded:	   The total number of bytes uploaded
    downloaded:  The total number of bytes downloaded
    left:        The number of bytes left to download for this client
    port:        The TCP port this client listens on
    compact:     Whether or not the client accepts a compacted list of peers or not
    '''
    parameters = {
      # 'info_hash': self.torrent.info_hash,
      'peer_id': self.peer_id,
      'port': 6889,
      'uploaded': uploaded,
      'downloaded': downloaded,
      'compact': 1,
    }

    if first:
      parameters['event'] = 'started'

    url = self.torrent['announce'] + '?' + urlencode(parameters)
    print("Parameters: ",parameters)
    print("URL: ",url)

  def calculate_peer_id(self):
    '''
    Generates and returns a Unique Peer ID.
    Peer ID is a parameter sent to the tracker in the GET request.
    There are two methods for generating the peer IDs.
    This implementation uses the Azureus-Style '-PC1000-<Unique-Characters>'.
    '''
    # generates 12 random numbers and appends them to the -PC1000- prefix
    return '-PC1000-' + ''.join([str(random.randint(0,9)) for _ in range(12)])



#Testing 
if __name__ == '__main__':
  test = Tracker(decode("test.torrent"))
  # print ("torrent", test.torrent)
  test.connect(first=True)
  print ("Peer ID", test.peer_id)