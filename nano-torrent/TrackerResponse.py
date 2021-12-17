import aiohttp
import random
import asyncio
import logging
import socket
from urllib.parse import urlencode
from bencoding import decode
from torrent import Torrent
from struct import unpack
from tracker import decode_port

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
      logging.debug('Tracker Responded with Dictionary-model peers')
      raise NotImplementedError()
    else:
      logging.debug('Tracker Responded with Binary-model peers')
      peers = [peers[i:i+6] for i in range(0,len(peers),6)]

      return [(socket.inet_ntoa(peer[:4]), decode_port(peer[:4])) for peer in peers] #socket.inet_ntoa: converts a 32-bit packed ip address to the standard dotted format. # This line converts the list of peers to a tuple.

