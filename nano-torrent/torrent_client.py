
import asyncio
import logging 
import time
from asyncio import Queue
from collections import namedtuple, defaultdict

from piece_manager import PieceManager
from peer_connection import PeerConnection, MAX_PEER_CONNECTION
from tracker import Tracker


class TorrentClient:
  '''
  The torrent client is responsible for the peer to peer connections to either leech of or seed to the peer.
  It also makes periodic announce calls to the tracker to update its list of peers with new ones.
  The list of peers is added to a queue from which we consume them one by one.
  '''
  def __init__(self, torrent):
    self.tracker = Tracker(torrent)
    self.available_peers = Queue() # The list of peers that can seed the file (all the peers we got from the tracker)
    self.peers = [] #The list of peers that we are trying to establish connection with (the peers we consumed from the Queue)
    self.piece_manager = PieceManager(torrent) # Decided which pieces of the file to request and how we store them on disk
    self.abort = False

  async def start(self):
    '''
    The eventloop.
    Starts downloading the torrent.
    returns when the download is either completed or aborted.
    '''
    self.peers = [ 
      PeerConnection(
        self.available_peers,
        self.tracker.torrent.info_hash,
        self.tracker.peer_id,
        self.piece_manager,
        self.on_block_retrieved
        )
        for _ in(MAX_PEER_CONNECTION)]

    # Last time we made an announce call
    previous = None
    # Interval between announce calls
    interval = 30*60 # an initial value, the tracker is the one who decides the interval.

    while True: 
      # Handling the different expected outcomes from the download
      if self.piece_manager.complete:
        logging.info("Download Completed!")
        break
      if self.abort:
        logging.info("Download Aborted!")
        break
        
      current = time.time()
      if (not previous) or (previous+interval) < current:
        response = await self.tracker.connect(
        first = previous if previous else False, # first represents if this the first time we've contacted this tracker
        uploaded = self.piece_manager.bytes_uploaded,
        downloaded = self.piece_manager.bytes_downloaded
        )

        if response:
          previous = current
          interval = response.interval #set the interval to whichever interval the tracker sent
          self.empty_queue()
          for peer in response.peers:
            self.available_peers.put_nowait(peer) #Puts an item into the queue without blocking. If no free slot is immediately available, raises QueueFull.
      else:
        await asyncio.sleep(5)
    self.stop()

  def empty_queue(self):
    while not self.available_peers.empty():
      self.available_peers.get_nowait() #queue.get_nowait(): Removes and returns an item from the queue. Returns an item if one is immediately available, else raise QueueEmpty.

  
  def stop(self):
    '''
    stops the download.
    '''
    self.abort = True
    for peer in self.peers:
      peer.stop()

    self.piece_manager.close()
    self.tracker.close()

  def on_block_retrieved(self, peer_id, piece_index, block_offset, data):
    '''
    Called by peer connection when a peer has blocked the client

    :param peer_id: the id of the peer the block was retrieved from.
    :param piece_index: the piece index this block is a part of.
    :param block_offset: the block offset within its piece.
    :param data: the binary data retrieved.
    '''
    self.piece_manager.block_recieved(
      peer_id = peer_id,
      piece_index = piece_index,
      block_offset = block_offset,
      data = data
    )

  