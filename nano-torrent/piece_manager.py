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

      else:

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
