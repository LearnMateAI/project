# Docker, day to day

Everything here assumes a terminal **in `integrated-backend/` with the venv activated** —
> **Do not run compose from `components-Dinura/`.** Both folders' compose files hardcode the
> same `container_name`, so it either collides or — worse, after a `down` — succeeds and starts a second stack on that folder's pre-cutover snapshot. That looks exactly like your data disappearing.

Two containers, and nothing else is containerised. The API, the models and the frontend all run on the host.

| Container | Port | Holds |
|---|---|---|
| `learnmate-mongo` | 27018 → 27017 | PDFs (GridFS), page text, accounts, chat, resources, evaluations, jobs |
| `learnmate-qdrant` | 6335 → 6333, 6336 → 6334 | chunk embeddings |

Non-default host ports, deliberately: this machine already answers 27017 with a native
MongoDB and 6333 with another project's Qdrant. `LEARNMATE_MONGODB_URI` and the Qdrant URL
in `.env` match the numbers above.

---

## Every day

```bash
docker compose up -d        # start both
docker compose ps           # are they up, and healthy?
docker compose stop         # stop, keep the containers
docker compose start        # start them again
docker compose restart      # bounce in place
docker compose down         # remove containers, KEEP the data volumes
```

`ps` is the one to trust. `Up` is not the same as `healthy` — Mongo reports healthy only
once it has finished recovering its journal, and the API's first connection fails if you
race it. Both healthchecks poll every 10s.

**Stop uvicorn before any `stop` or `down`.** The job queue lives in the server process's
memory; pulling Mongo out from under a running job lands it as `failed`, and the next
server start marks the rest "Interrupted by a server restart".

Docker Desktop must be running first. If `docker` reports `failed to connect to the Docker
API at npipe:...dockerDesktopLinuxEngine`, that is all it means — start Docker Desktop and
wait for the whale to settle. Both containers carry `restart: unless-stopped`, so they come
back by themselves once the engine is up, and `up -d` is often unnecessary.

---

## Looking inside

```bash
docker compose logs -f              # both, following
docker compose logs -f mongo        # one service
docker compose logs --tail 50 qdrant
docker stats --no-stream            # CPU and memory, when the box feels slow
```

A **mongo shell** on the real database:

```bash
docker exec -it learnmate-mongo mongosh learnmate
```

Then, inside it:

```javascript
db.getCollectionNames()
db.users.countDocuments()
db.documents.find({}, {filename: 1, processing_status: 1})
db.jobs.find({status: "failed"}).sort({created_at: -1}).limit(5)
db.pdfs.files.find({}, {filename: 1, length: 1})     // GridFS
```

One-liner form, for when you just want a number:

```bash
docker exec learnmate-mongo mongosh learnmate --quiet \
  --eval 'db.getCollectionNames().forEach(function(c){ print(c + ": " + db[c].countDocuments()) })'
```

**Qdrant** has no shell — it is a distroless image, with no `sh`, no `curl`, not even `ls`.
Talk to it over HTTP from the host instead:

```bash
curl -s http://localhost:6335/collections
curl -s http://localhost:6335/collections/learnmate_chunks     # status, points_count
```

Its dashboard is at <http://localhost:6335/dashboard>.

`points_count` there and `db.chunks.countDocuments()` in Mongo will not always agree. Mongo
is the source of truth; a surplus in Qdrant is orphaned vectors from a deleted document, and
a re-ingest clears it.

---

## When something is wrong

**`/api/health` says `degraded`.** Read its `checks` block — it names which dependency
failed. Then `docker compose ps` to see whether the container is actually healthy, and
`docker compose logs` for why not.

**Is the port really answering?**

```bash
curl -s http://localhost:6335/healthz
docker exec learnmate-mongo mongosh --quiet --eval 'db.adminCommand("ping")'
```

**Something else stole the port.** `netstat -ano | grep 27018` names the PID. Note this is
the failure that gave the whole project its odd port numbers, so it is worth checking early.

**Qdrant crash-loops after an image change.** Its on-disk segment format is not backward
compatible — 1.18 cannot read 1.12 storage and dies with `unknown variant 'on_disk'`. Fix it
with the vectors-only reset below, not with `down -v`.

**Start from scratch on one container** without touching data:

```bash
docker compose up -d --force-recreate mongo
```

---

## Resets, from safest to worst

**Vectors only.** The one you almost always want. Embeddings are derived from page text in
Mongo, so this costs a re-ingest and nothing else:

```bash
docker compose down
docker volume rm integrated-backend_qdrant_storage
docker compose up -d
```

**Everything.** `down -v` deletes both volumes:

```bash
docker compose down -v
docker compose up -d
```

> **`down -v` is not recoverable.** MongoDB holds the only copy of the uploaded PDFs, the
> accounts and the chat history — nothing regenerates them. You would be re-registering and
> re-uploading from scratch. Take the dump below first, or run the vectors-only reset
> instead. The `-v` is the entire difference between the two, on commands that otherwise
> look identical.

---

## Backups

Both tools are present in the images — verified, not assumed.

**Mongo — dump and restore:**

```bash
# dump to ./backup on the host
docker exec learnmate-mongo mongodump --db learnmate --archive=/tmp/lm.archive
docker cp learnmate-mongo:/tmp/lm.archive ./backup/lm-$(date +%Y%m%d).archive

# restore
docker cp ./backup/lm-20260814.archive learnmate-mongo:/tmp/lm.archive
docker exec learnmate-mongo mongorestore --archive=/tmp/lm.archive --drop
```

`--drop` replaces the collections in the archive. Stop uvicorn first.

**Qdrant — snapshot:**

```bash
curl -X POST http://localhost:6335/collections/learnmate_chunks/snapshots
curl -s http://localhost:6335/collections/learnmate_chunks/snapshots
curl -X DELETE http://localhost:6335/collections/learnmate_chunks/snapshots/<name>
```

Snapshots are written **inside the volume**, and a full one is roughly half a gigabyte
against this corpus. Delete them when done, or they quietly become the largest thing on the
disk. Given that the vectors are rebuildable from Mongo, a re-ingest is usually the better
answer than keeping snapshots around.

**Copying a whole volume** — this is how the cutover was done, and it works for any
before-I-break-something snapshot:

```bash
docker volume create integrated-backend_mongo_data_backup
docker run --rm \
  -v integrated-backend_mongo_data:/from:ro \
  -v integrated-backend_mongo_data_backup:/to \
  alpine cp -a /from/. /to/
```

Containers must be stopped, `cp -a` is required (it preserves the uid Mongo runs as), and on
Git Bash prefix the command with `MSYS_NO_PATHCONV=1` or the `/from` paths get rewritten
into Windows paths.

---

## Volumes

```bash
docker volume ls --filter name=integrated-backend
docker volume inspect integrated-backend_mongo_data

# how big is the corpus?
docker run --rm -v integrated-backend_mongo_data:/m alpine du -sh /m
```

Volumes are named, not bind mounts into the repo — Qdrant's storage engine misbehaves on a
Windows bind mount, and it keeps `git status` clean. They survive `down`, a reboot and an
image upgrade; only `down -v` or an explicit `docker volume rm` removes them.

The pre-cutover volumes `components-dinura_mongo_data` and `components-dinura_qdrant_storage`
still exist, holding the 2026-08-14 snapshot as a rollback. Once the cutover has proven
itself:

```bash
docker volume rm components-dinura_mongo_data components-dinura_qdrant_storage
```

---

## Housekeeping

```bash
docker system df                  # what is actually using the disk
docker image prune                # dangling images
docker builder prune              # build cache, usually the biggest win
```

Never `docker system prune --volumes` on this machine. It reaches across every project,
takes unused volumes with it, and this box also runs `simplytask-backend` and
`helpmedai-qdrant` for unrelated work.
