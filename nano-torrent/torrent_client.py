
import asyncio
import logging 
from asyncio import Queue
from collections import namedtuple, defaultdict
from piece_manager import PieceManager


from tracker import Tracker

class TorrentClient:
  '''
  The torrent client responsible for the peer to peer connections to either leech of or seed to the peer.
  It also makes periodic announce calls to the tracker to update its list of peers with new ones.
  The list of peers is added to a queue from which we consume them one by one.
  '''
  def __init__(self, torrent):
    self.tracker = Tracker(torrent)
    self.available_peers = Queue() # The list of peers that can seed the file (all the peers we got from the tracker)
    self.peers = [] #The list of peers that we are trying to establish connection with (the peers we consumed from the Queue)
    # self.piece_manager = PieceManager(torrent) # Decided which pieces of the file to request and how we store them on disk
    self.abort = False
