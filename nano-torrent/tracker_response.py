
import logging
import socket
from urllib.parse import urlencode
from bencoding import decode
from torrent import Torrent
from struct import unpack
# from tracker import decode_port

def decode_port(port):
  '''
  converts a 32-bit packed binary number to int
  '''
  return unpack(">H", port)[0]


class TrackerResponse:
  '''
  The tracker's response after a successful get request to the announce url.
  The tracker can respond in several ways in case of successful communication,
  so this class handles expected responses.
  '''

  def __init__(self, response):
    self.response = response

  
  @property
  def peers(self):
    '''
    if the announce url had the right parameters, the tracker responds with a list of peers that has the torrent files
    this getter defines a list of tuples for each peer constructed as (ip, port)
    '''
    # this implementation only handles binary string model of peers
    # Binary string model: each peer would have 6 bytes in the continous string, the first 4 are its IP and the last 2 are the TCP port.
    # TODO: Handle dictionary-model peers
    peers = self.response['peers']
    if type(peers) == list:
      logging.info('Tracker Responded with Dictionary-model peers')
      raise NotImplementedError()
    else:
      logging.info('Tracker Responded with Binary-model peers')
      peers = [peers[i:i+6] for i in range(0,len(peers),6)]
      
      # print("\n\nPeers: ", peers)
      # socket.inet_ntoa: converts a 32-bit packed ip address to the standard dotted format.
      # This line converts the list of peers to a tuple.
      return [(socket.inet_ntoa(peer[:4]), decode_port(peer[4:])) for peer in peers] 


  @property
  def incomplete(self):
    '''
    Number of peers that haven't completed their download (aka, number of leechers)
    '''
    return self.response.get('incomplete', 0)

  @property
  def complete(self):
    '''
    Number of peers that have completed the download (aka, number of seeders)
    '''
    return self.response.get('complete', 0)

  @property 
  def interval(self):
    '''
    The interval in seconds that the client must wait before contacting the tracker again
    '''
    return self.response.get('interval', 0)

  @property
  def failure(self):
    '''
    The reason why the tracker request failed, if the request succeeded, this would be set to None.
    '''
    return decode(self.response.get('failure reson'))

  @property
  def __str__(self):
    return "Incomplete: {incomplete}\nComplete: {complete}\nInterval: {interval}\nPeers: {peers}\n".format(
      incomplete = self.incomplete,
      complete = self.complete,
      interval = self.interval,
      peers = self.peers
    )