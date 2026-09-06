# Finishing the LazyLibrarian setup

LazyLibrarian is the book/audiobook grabber (Readarr was retired). It's the one
app in this stack that is **not** wired up by Prowlarr's "Apps" sync — you have
to give it an indexer feed by hand. If books never download, this is almost
always why.

Open it at **http://localhost:5299**.

---

## 1. Downloader — point it at qBittorrent

**Config → Downloaders → Torrent** section:

| Field | Value |
|---|---|
| Enable | qBittorrent |
| Host | `gluetun`  ← not `qbittorrent`, not `localhost` |
| Port | `8080`  ← the internal port, not 18080 |
| User / Pass | your qBittorrent WebUI login |
| Download dir | `/data/downloads` |

`gluetun:8080` is required because qBittorrent shares the VPN container's
network. Save, then use LazyLibrarian's **Test** button if it offers one.

## 2. Processing — where finished books land

**Config → Processing:**

- **Destination / Download dir:** `/data/downloads`
- **eBook destination:** `/data/media/books`
- **Audiobook destination:** `/data/media/audiobooks`

These are container paths. In Windows they are `G:\MediaStack\media\books` and
`...\audiobooks` — the same folders Audiobookshelf serves, so anything imported
shows up there automatically.

> Make sure those folders exist on the drive first, or import silently fails.

## 3. Indexer — the step that's usually missing

LazyLibrarian needs a **Torznab** feed pasted in manually.

**Get the feed from Prowlarr** (`http://localhost:9696`):
1. Go to **Indexers**, pick an indexer that carries books/audiobooks.
2. Copy its **Torznab feed URL**. It looks like
   `http://prowlarr:9696/<indexer-id>/api` — use the `prowlarr:9696` container
   name, not `localhost`, since LazyLibrarian is calling from inside Docker.
3. Get the **API key** from Prowlarr → **Settings → General**.

**Add it in LazyLibrarian** — **Config → Searching → Torznab**:
- **Name:** anything (e.g. `Prowlarr - IPTorrents`)
- **Host / URL:** the Torznab URL from above
- **API key:** the Prowlarr API key
- **Enable** it for **books** and/or **audiobooks**

Repeat for each indexer you want it to search. Public indexers (1337x, etc.)
work here too and have no ratio requirement.

## 4. Turn on audiobook searching

LazyLibrarian treats ebooks and audiobooks separately. In **Config → Processing
/ Searching**, make sure **audiobook** types are enabled and that an audiobook
destination is set — otherwise it will only ever look for ebooks.

## 5. Test it

1. **Authors → Add Author** → search a well-known author → add.
2. Mark a book/audiobook as **Wanted**.
3. Run a **Search**.
4. Watch **qBittorrent** (`http://localhost:18080`) — the torrent should appear.
5. When it finishes, LazyLibrarian imports it to `/data/media/books` or
   `/data/media/audiobooks`, and Audiobookshelf picks it up on its next scan.

---

## Troubleshooting

| Symptom | Cause |
|---|---|
| Searches return nothing | No Torznab provider configured (step 3), or not enabled for the right media type |
| Finds results, nothing reaches qBittorrent | Downloader host wrong — must be `gluetun` port `8080` |
| Downloads finish but never appear in the library | Processing destinations wrong, or the folders don't exist |
| Only ebooks, never audiobooks | Audiobook types not enabled (step 4) |

## The low-effort alternative

Book metadata is messy and LazyLibrarian is the fussiest app here. For
audiobooks you can always skip it entirely: drop files into

```
G:\MediaStack\media\audiobooks\<Author>\<Book Title>\
```

and Audiobookshelf will scan and tag them. One folder per book. This always
works and is often faster than fighting an auto-grab.
