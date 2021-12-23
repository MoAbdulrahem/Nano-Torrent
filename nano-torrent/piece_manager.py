import os
import math

from collections import namedtuple

from piece import Piece
from block import Block
from peer_connection import REQUEST_SIZE

# A factory for creating tuples representing pending requests that have likely times out, so we can re-issue them.
PendingRequest = namedtuple('PendingRequest', ['block', 'added'])

class PieceManager:
  '''
  Responsible for checking all the pieces of the torrent, which pieces we have downloaded, 
  and which pieces we are going to request from the peers.

  Responsible for storing the pieces on disk.
  '''
  def __init__(self, torrent):
    self.torrent = torrent
    self.peers = {}
    self.pending_blocks = []
    self.missing_pieces = []
    self.ongoing_pieces = []
    self.have_pieces = []
    self.max_pending_time = 300000 # 5*60*1000 = 5 minutes
    self.missing_pieces = self.initiate_pieces()
    self.total_pieces = len(torrent.pieces)
    self.fd = os.open(self.torrent.output_file, os.O_RDWR | os.O_CREAT)

  def initiate_pieces(self) -> Piece:
    '''
    Constructs the list of Blocks based on the number of pieces and the REQUEST_SIZE for this torrent
    '''
    torrent = self.torrent
    pieces = []
    total_pieces = len(torrent.pieces)
    std_piece_blocks = math.ciel(torrent.piece_length / REQUEST_SIZE) # number of pieces = length/request_size 
    #and we take the upper cieling for it the last block would be smaller than the other pieces but would still take a request.

    for index, hash_value in enumerate(torrent.pieces):

      if index < (total_pieces -1): 
        blocks = [Block(index, offset*REQUEST_SIZE, REQUEST_SIZE) for offset in range(std_piece_blocks)]

      else: # This is the last piece

        last_length = torrent.total_size % torrent.piece_length
        num_blocks = math.ciel(last_length/ REQUEST_SIZE)
        blocks = [Block(index, offset*REQUEST_SIZE, REQUEST_SIZE) for offset in range(num_blocks)]

        if last_length % REQUEST_SIZE > 0:
          # last block of the last piece might be smaller than the ordinary request size
          last_block = blocks[-1]
          last_block.length = last_length % REQUEST_SIZE
          blocks[-1] = last_block

      pieces.append(Piece(index, blocks, hash_value))
    return pieces

  
  def close(self):
    '''
    Closes opened files
    '''
    if self.fd:
      os.close(self.fd)

  @property
  def complete(self):
    '''
    Checks whether all the torrent pieces are downloaded or not.

    Returns True if all the pieces are downloaded, False otherwise.
    '''

    return len(self.have_pieces) == self.total_pieces

  @property
  def bytes_downloaded(self):
    '''
    returns the size in bytes for the pieces that have been downloaded.

    pieces that we have blocks of, but are not yet fully downloaded are not counted.
    '''

    return len(self.have_pieces) * self.torrent.piece_legnth

  @property
  def bytes_uploaded(self):
    '''
    returns the size of pieces we have uploaded
    '''
    return 0 # seeding is not implemented yet

  
  def add_peer(self, peer_id, bitfield):
    '''
    Adds a peer and the bitfield representing the pieces that the peer have.

    :param peer_id: the id of the peer.
    :param bitfield: is a message that the peer sends us, it consists of a binary sequence with the same length 
    as the number of pieces, each digit in the binary represents a piece, so a 0 means a missing piece, and 1 means
    the peer has that piece
    '''
    self.peers[peer_id] = bitfield

  def update_peer(self, peer_id, index):
    '''
    updates the information about which piees a peer has. (reflects a Have message)
    '''
    if peer_id in self.peers:
      self.peers[peer_id][index] = 1

  