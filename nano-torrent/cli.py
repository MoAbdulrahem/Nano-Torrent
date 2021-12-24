import logging
import asyncio
import argparse
from concurrent.futures import CancelledError
from torrent import Torrent
from torrent_client import TorrentClient

def main():
  try:
    parser = argparse.ArgumentParser()
    parser.add_argument('torrent', help='path to the .torrent file')
    parser.add_argument('-l', '--log', action='store_true', help='Show logs')

    args = parser.parse_args()
    if args.log:
      logging.basicConfig(level = logging.INFO)

    # Asyncronous IO
    loop = asyncio.get_event_loop()
    client = TorrentClient(Torrent(args.torrent))
    task = loop.create_task(client.start())

    try:
      loop.run_until_complete(task)
    except CancelledError:
      logging.warning("The evenloop was cancelled")
  
  except KeyboardInterrupt:
    logging.info("Exitting")
    client.stop()
    task.cancel()


main()