

from hashlib import sha1

from block import Block

class Piece:
  '''
  The torrent contents are divided into pieces of the same size -except for the final piece which most likely will be smaller-

  The piece size is usually larger than what can be fit in a single request,
  so, they are further divided into a smaller unit called Blocks -in the unofficial BitTorrent specs-.
  '''

  def __init__(self, index, blocks, hash_value):
    self.index = index
    self.blocks = blocks
    self.hash = hash_value

  def reset(self):
    '''
    Makes the status of all the blocks "Missing."
    '''
    for block in self.blocks:
      block.status = Block.Missing

  def next_request(self):
    '''
    Determines the next block to be requested.
    '''
    missing = [block for block in self.blocks if block.status is Block.Missing] # make a list of all missing blocks

    if missing: # if we got missing blocks
      missing[0].status = Block.Pending #change the status of the first block to pending and return it
      return missing[0]

    return None

  def block_recieved(self, offset, data: bytes):
    '''
    Updates the block status in case of a successful download of a block.

    :param offset: the block offset inside the piece (remember: the piece is a continous byte string)
    :param data: The block data.
    '''

    matches = [block for block in self.blocks if block.offset == offset] # get the block to be updated
    block = matches[0] if matches else None
    if block:
      block.status = Block.Retrieved
      block.data = data
    else:
      logging.warning("Block was not found at offset {offset}.".format(offset=offset))
    
  
  def is_complete(self) -> bool:
    '''
    Checks of the SHA1 hash of all the blocks combined matches the hash for the piece (found in the info dict from the torrent meta-info)

    :return: boolean.
    '''
    piece_hash = sha1(self.data).digest()
    return self.hash == piece_hash

  
  @property
  def data(self):
    '''
    Concatenates all the blocks, and returns the data obtained from that.
    '''
    retrieved = sorted(self.blocks, key=lambda b: b.offset)
    blocks_data = [b.data for b in retrieved]
    
    return b''.join(blocks_data)