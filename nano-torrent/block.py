

class Block:
  '''
  Represent a block of a piece.
  
  The piece size is almost always larger than what can be fit in a single request.
  Therefore, it is further divided into Blocks.
  All blocks are of the same size as the REQUEST_SIZE, except for the final block which will be most likely smaller.
  '''

  # Block status
  Missing = 0
  Pending = 1
  Retrieved = 2

  def __init__(self, piece, offset, length):

    self.piece = piece
    self.offset = offset 
    self.length = length
    self.status = Block.Missing
    self.data = None