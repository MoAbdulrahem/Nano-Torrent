import os
import math
import logging
import time

from collections import namedtuple, defaultdict

from piece import Piece
from block import Block
from peer_connection import REQUEST_SIZE

# A factory for creating tuples representing pending requests that have likely times out, so we can re-issue them.
PendingRequest = namedtuple('PendingRequest', ['block', 'added'])

class PieceManager:
  '''
  Responsible for checking all the pieces of the torrent, which pieces we 
  have downloaded, 
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
    Constructs the list of Blocks based on the number of pieces and the 
    REQUEST_SIZE for this torrent
    '''
    torrent = self.torrent
    pieces = []
    total_pieces = len(torrent.pieces)
    std_piece_blocks = math.ciel(torrent.piece_length / REQUEST_SIZE) # number of pieces = length/request_size 
    #and we take the upper cieling for it the last block would be smaller 
    # than the other pieces but would still take a request.

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

    pieces that we have blocks of, but are not yet fully downloaded are 
    not counted.
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
    :param bitfield: is a message that the peer sends us, it consists of 
    a binary sequence with the same length 
    as the number of pieces, each digit in the binary represents a piece, 
    so a 0 means a missing piece, and 1 means the peer has that piece
    '''
    self.peers[peer_id] = bitfield

  def update_peer(self, peer_id, index):
    '''
    updates the information about which piees a peer has. (reflects a Have
     message)
    '''
    if peer_id in self.peers:
      self.peers[peer_id][index] = 1

  def remove_peer(self, peer_id):
    '''
    removes a peer from the list of peers (if the connection to the peer
     was dropped)
    '''
    if peer_id in self.peers:
      del self.peers[peer_id]

  def next_request(self, peer_id) -> Block:
    '''
    Get the next Block that should be requested from the given peer.

    If there are no more blocks left to retrieve or if this peer does not
    have any of the missing pieces, return None
    '''
    # This implementation uses Rarest-Piece-First algorithm, in which we 
    # determine the pieces with the lowest number of peers that have them,
    # and start downloading them.
    # The download should be randomized, as  all the leechers downloading
    # the piece with the lowest available peer would be counter-productive.
    #
    # The algorithm tries to download the pieces in sequence and will try
    # to finish started pieces before starting with new pieces.
    #
    # 1. Check any pending blocks to see if any request should be reissued
    #    due to timeout
    # 2. Check the ongoing pieces to get the next block to request
    # 3. Check if this peer have any of the missing pieces not yet started

    if peer_id not in self.peers:
      return None

    block = self.expired_requests(peer_id)
    if not block: #no expired requests, so request for the next block
      block = self.next_ongoing(peer_id)
      if not block: #no next_ongoing requests
        block  = self.get_rarest_piece(peer_id).next_request()
    
    return block

  

  def block_recieved(self, peer_id, piece_index, block_offset, data):
    '''
    This method must be called when a block has successfully been retrieved
    by a peer.

    Once a full piece has been retrieved, a SHA1 hash control is made. If
    the check fails all the pieces blocks are put back in missing state to
    be fetched again. If the hash succeeds the partial piece is written to
    disk and the piece is indicated as Have.
    '''

    logging.debug('Received block {block_offset} for piece {piece_index} from peer {peer_id}: '.format(
      block_offset=block_offset,
      piece_index=piece_index,
      peer_id=peer_id
      ))

    # Remove from pending requests
    for index, request in enumerate(self.pending_blocks):
      if request.block.piece == piece_index and request.block.offset == block_offset:
        del self.pending_blocks[index]
        break

    pieces = [p for p in self.ongoing_pieces if p.index == piece_index] # get the piece 
    # that we want to chack the hash value of.
    piece = pieces[0] if pieces else None 
    if piece:
      piece.block_received(block_offset, data)
      if piece.is_complete():
        if piece.is_hash_matching():
          self._write(piece)
          self.ongoing_pieces.remove(piece)
          self.have_pieces.append(piece)
          complete = (self.total_pieces - len(self.missing_pieces) - len(self.ongoing_pieces))
          logging.info(
              '{complete} / {total} pieces downloaded {per:.3f} %'.format(
                complete=complete,
                total=self.total_pieces,
                per=(complete/self.total_pieces)*100
                ))
        else:
          logging.info('Discarding corrupt piece {index}'.format(
            index=piece.index
            ))
            
          piece.reset()
    else:
      logging.warning('Trying to update piece that is not downloaded!')

  
  def expired_requests(self, peer_id) -> Block:
    '''
    Goes through the requested blocks and checks if any of them has
    been requested for longer than the MAX_PENDING_TIME. If found,
    return them to be reissued.

    if none is found return None.
    '''

    current = int(round(time.time()*1000)) #current time in seconds
    for request in self.pending_blocks: #pending_blocks contain tuples of PendingRequests,
      # which consist of the block and the time it was added
      if self.peers[peer_id][request.block.piece]:
        if request.added + self.max_pending_time < current:
          logging.info('Re-requesting block {block} for piece {piece}'.format(
            block=request.block.offset,
            piece=request.block.piece
          ))
          
          request.added = current #reset expiration rimer
          return request.block

    return None # No blocks need to be re-requested

  def self_ongoing(self, peer_id) -> Block:
    '''
    Goes through ongoing pieces and returns the next block to be downloaded
    or None if there are no blocks left.
    '''
    for piece in self.ongoing_pieces:
      if self.peers[peer_id][piece.index]: # are there any blocks left to
        # download in this piece?
        block = piece.next_request()
        if block:
          self.pending_blocks.append(
            PendingRequest(block, int(round(time.time() * 1000)))
          )
          return Block
    return None

  def get_rarest_piece(self, peer_id):
    '''
    The algorithm we follow to determine which pieces would be downloaded
    first.

    Goes through the list of missing_pieces, and returns the rarest one
    (the one with the least number of seeders)
    '''
    piece_count = defaultdict(int) # a default dict is a dict that doesn't raise key error
    # if u access a non-existing key, it gets added and assigned the default value, in our case int -> 0
    for piece in self.missing_pieces:
      if not self.peers[peer_id][piece.index]:
        continue
      for p in self.peers:
        if self.peers[p][piece.index]:
          piece_count[piece] += 1

    rarest_piece = min(piece_count, key=lambda p: piece_count[p])
    self.missing_pieces.remove(rarest_piece)
    self.ongoing_pieces.append(rarest_piece)
    return rarest_piece