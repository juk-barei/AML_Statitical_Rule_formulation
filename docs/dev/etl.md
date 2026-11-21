 1. What each process actually opens

 ETL.py is not one process. It is a parent + up to 5 worker processes (MAX_WORKERS = 5, DEFAULT_WORKERS = 5 —
 src/scripts/ETL.py:63-64).

 Parent process (run_etl, src/scripts/ETL.py:1494):
 - source_engine and local_engine, each pool_size=1 (:1508-1513, default at :313).
 - Used only for metadata: inspect(), COUNT(*), MIN/MAX (:369, :382) — borrowed and returned one at a time.
 - Before forking workers it calls source_engine.dispose() and local_engine.dispose() (:1627-1628), so no pooled
   connections leak into the children.
 - During the run it creates poll_engine (local, pool_size=1) and polls status every 5 s (:1639, PROGRESS_POLL_SECONDS
   = 5 at :68).

 Each worker process (worker_init, src/scripts/ETL.py:948-965):
 - One source engine, pool_size=1 → exactly 1 remote socket.
 - One local engine, pool_size=2 → one connection holds the COPY stream, the second is for progress writes (:953-961,
   :1066).
 - The source connection is opened once per shard and held for the whole shard in REPEATABLE READ (:1063-1064);
   batches of 50k rows are read on that same connection (:1080), then pushed through COPY on the local raw connection
   and committed (:1092-1098).
 - So per worker: 1 remote + 2 local sockets, reused sequentially, not reconnected per batch.

 Peak with defaults (--workers 5):

 ┌──────────────────┬──────────────┬─────────────────────┬───────────────────────────────────────────┬───────────────┐
 │ Endpoint         │ ETL parent   │ ETL workers         │ Profiler                                  │ Total         │
 ├──────────────────┼──────────────┼─────────────────────┼───────────────────────────────────────────┼───────────────┤
 │ Remote/online DB │ 0 during run │ 5 (1 each)          │ 1–2 (pool_size=4,                         │ 6–7 sockets   │
 │                  │              │                     │ profile_databases.py:117)                 │               │
 ├──────────────────┼──────────────┼─────────────────────┼───────────────────────────────────────────┼───────────────┤
 │ Local PostgreSQL │ 1 (poll)     │ 10 (2 each)         │ 0                                         │ 11 sockets    │
 ├──────────────────┼──────────────┼─────────────────────┼───────────────────────────────────────────┼───────────────┤
 │ Local disk       │ report + CSV │ WAL/fsync per batch │ CSV writes                                │ separate      │
 │                  │              │                     │                                           │ files         │
 └──────────────────┴──────────────┴─────────────────────┴───────────────────────────────────────────┴───────────────┘

 profile_databases.py profiles sources sequentially and does one aggregate query per table (:59), so it normally
 checks out 1 connection at a time; the pool can hold up to 4 open, and the first source's connection stays open in
 engines while the second is profiled (:118, dispose at :151).

 2. Where "switching" does and does not happen

 There are four different layers people conflate:

 1. Between the two scripts — no switching. They are separate processes with separate address spaces, file
    descriptors, and sockets. The kernel schedules CPU time between them (context switches), but that is CPU sharing,
    not connection sharing. Neither script knows the other exists.
 2. Inside one connection — yes, sequential multiplexing. PostgreSQL's wire protocol is request/response per
    connection. One worker sends a SELECT, waits, receives the batch, then sends COPY on a different connection. One
    socket carries one operation at a time; that is time-division, not simultaneous.
 3. Across workers — true parallelism. 5 worker processes = 5 remote connections genuinely in flight at once,
    interleaved packet-by-packet by the kernel over one NIC.
 4. Server side — depends on the host. Direct Postgres = one backend process per client connection (fork per
    connection). If the host is behind Supavisor/PgBouncer in transaction mode, many client connections are mapped
    onto fewer backends and a backend is switched between clients per transaction. That is the only place real
    connection switching occurs.

 3. Hardware path for one 50k batch

 ```
   pandas read_sql_query (client RAM)
     → psycopg → libpq wire protocol
     → kernel send/recv socket buffers
     → TCP/IP stack → NIC (packet queues, RSS)
     → router/switch → remote LB → remote kernel → one Postgres backend
        → shared_buffers / disk read → row serialization → back over TCP

   then, on the local leg:
   pandas DataFrame → StringIO CSV → raw_connection COPY (one big getvalue() string)
     → kernel socket → local Postgres backend → WAL write + commit → fsync
 ```

 Hardware involved and why it matters:
 - NIC / TCP stack: 11 local sockets and 6–7 remote sockets are just logical streams; the NIC serializes packets.
   Bandwidth and RTT are shared, so the profiler's queries slow the ETL's reads and vice versa.
 - Client CPU/RAM: each worker holds ~50k rows as a DataFrame and as a CSV string (buffer.getvalue()), so ~15 workers'
   worth of buffers at 5 workers.
 - Local disk: one COMMIT per batch (:1098) = one WAL flush/fsync; 5 workers committing in parallel creates write
   contention.
 - Remote server CPU/disk: LIMIT … OFFSET n still walks n rows, so deep offsets get progressively slower
   (build_batch_query, :977-990). Five concurrent scans plus the profiler's COUNT(DISTINCT …) full scans compete for
   the same remote disk and CPU.
 - Remote memory/vacuum: the REPEATABLE READ transaction is held for a whole shard (:1063), so a long ETL run pins the
   snapshot and delays vacuum on a busy source.
 - Connection limits: each socket has an ephemeral local port and a server-side backend slot. Check max_connections on
   both ends; a pooler's client limit on the host can be the binding constraint.

 4. What this means in practice

 You are not "sharing 2 connections." You are running two independent workloads that merely contend for the same
 remote database and the same laptop resources. No switching bug, no multiplexing surprise — just competition.

 To confirm the real numbers while both run:

 ```bash
   ss -tnp | grep ':5432'                      # sockets per process
   psql -c "SELECT usename, state, count(*) FROM pg_stat_activity GROUP BY 1,2"
 ```

 If the remote is small or connection-limited, profile first and ingest after, or lower --workers — the profiler's
 COUNT(DISTINCT) scans are the expensive half, not the connection count.
