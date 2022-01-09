# Nano-Torrent
A BitTorrent client written in python. I built this as a side-project to learn more about networks and asynchronous IO in python `asyncio`.

# Set up
1. Clone this repo.
```bash
git clone https://github.com/MoAbdulrahem/Nano-Torrent
```
2. Navigate to the project's directory
```bash
cd Nano-Torrent/nano-torrent
```
3. Create a virtual environment.
```bash
virtualenv --python=python3 nano
```
4. Activate the virtualenv.
```bash
source nano/bin/activate
```
5. Install dependancies.
```bash
pip install -r requirements.txt
```

# Usage
```bash
python cli.py [-h] [-l] torrent
```
`-h` Show help.

`-l` Show logs.

`torrent` is the path to the torrent file.

# Limitations
Right now, Nano-Torrent can only download single-file silngle-piece torrents.

# Helpful Resources
### Asyncio
[An introduction to Python's asyncio](https://markuseliasson.se/article/introduction-to-asyncio/)

[How does async/await work in Python 3.5?](https://snarky.ca/how-the-heck-does-async-await-work-in-python-3-5/)
### Implementing BitTorrent
[Unofficial BitTorrent Specs](https://wiki.theory.org/BitTorrentSpecification)

