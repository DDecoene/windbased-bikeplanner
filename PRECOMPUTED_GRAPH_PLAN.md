# Pre-computed Belgian RCN Network Graph

## Context

100km+ routes fail because the Overpass API times out on 60km radius queries. Even successful queries take 10-28s for graph building. This won't scale. Solution: download the entire Belgian RCN network once, store it in SQLite + pickle, and serve routes from local data. Per-request time drops from 10-30s to 1-5s, and large routes stop failing.

## Architecture

```
Current:  Request → Overpass API (slow/fails) → build graph → route
New:      Weekly cron → SQLite + pickle on disk
          Startup   → load knooppunt graph (pickle, ~20MB) into memory
          Request   → query SQLite for lookups + in-memory K for DFS → route (fast)
```

**Hybrid storage:**
- **SQLite** (`graph_data/rcn_network.db`) — full network: ~100K nodes with coords, ~200K edges with bearings/lengths. R-tree spatial index for nearest-node lookups. Queried on demand, never fully loaded into memory.
- **Pickle** (`graph_data/knooppunt_graph.pickle`) — condensed knooppunt graph (~3K nodes, ~8K edges with `full_path`). Loaded into memory at startup (~5-20MB). Required for DFS loop finding.

**What stays per-request:** Wind effort (depends on current weather), approach path (depends on start location), DFS loop finding, geometry extraction.

## Files to Create

### 1. `scripts/build_graph.py`
Standalone script to download ALL Belgian RCN data and build the local database.
- Overpass query using Belgium area filter: `area["ISO3166-1"="BE"]`, 300s timeout, 512MB maxsize
- Calls existing `overpass.build_graph()` and `overpass.build_knooppunt_graph()`
- Writes nodes + edges to SQLite with R-tree spatial index
- Serializes knooppunt graph K to pickle
- Writes `graph_data/metadata.json` (build timestamp, node/edge counts)
- Atomic writes (temp files → rename) to prevent corruption
- Run: `python -m scripts.build_graph`

### 2. `app/graph_manager.py`
Singleton that manages the pre-built data.
- `load()` — load knooppunt graph pickle into memory, open SQLite connection
- `get_knooppunt_subgraph(lat, lon, radius_m)` — filter K nodes within radius, return mutable copy
- `nearest_node(lat, lon)` — R-tree spatial query on SQLite
- `nearest_knooppunt(lat, lon)` — R-tree query filtered to rcn_ref nodes
- `get_edge_data(node_pairs)` — batch lookup of edge bearings/lengths from SQLite
- `get_node_coords(node_ids)` — batch lookup for geometry extraction
- `build_approach_subgraph(lat, lon, radius_m=5000)` — small networkx subgraph from SQLite for Dijkstra approach path
- Thread-safe: read-only SQLite (per-thread connections via `threading.local()`), shared K in memory

### 3. `scripts/__init__.py`
Empty, makes scripts importable.

## Files to Modify

### 4. `app/overpass.py`
- Add `fetch_full_belgium_rcn()` — area-based Overpass query for all Belgium, 300s timeout

### 5. `app/routing.py` (core change)
- Add `_add_knooppunt_effort_dynamic(K, graph_mgr, wind_speed, wind_dir)` — computes wind effort on K edges by batch-querying edge bearings from SQLite
- Modify `find_wind_optimized_loop()` with dual code path:
  - **If graph loaded:** use graph_manager for lookups + in-memory K for DFS
  - **If not loaded (fallback):** current Overpass per-request flow unchanged

### 6. `app/main.py`
- Load graph at startup (`GraphManager.get_instance().load()`)
- Extend `/health` to report graph status + metadata

### 7. `docker-compose.yml`
- Add `graph_data` named volume, mount to backend

### 8. `Dockerfile`
- Create `graph_data/` dir, add to `chown` in CMD

### 9. `.gitignore`
- Add `graph_data/`

## SQLite Schema

```sql
-- Nodes table
CREATE TABLE nodes (
    id INTEGER PRIMARY KEY,
    lat REAL NOT NULL,
    lon REAL NOT NULL,
    rcn_ref TEXT  -- NULL for non-knooppunt nodes
);

-- R-tree spatial index for fast nearest-node queries
CREATE VIRTUAL TABLE nodes_rtree USING rtree(
    id, min_lat, max_lat, min_lon, max_lon
);

-- Edges table (bidirectional: both u→v and v→u stored)
CREATE TABLE edges (
    source_id INTEGER NOT NULL,
    target_id INTEGER NOT NULL,
    length REAL NOT NULL,
    bearing REAL NOT NULL,
    PRIMARY KEY (source_id, target_id)
);
CREATE INDEX idx_edges_source ON edges(source_id);
```

## Concurrency Safety

- Knooppunt graph K in memory: shared read-only, per-request `.copy()` of subgraph for mutation (adding effort)
- SQLite: WAL mode, read-only access, per-thread connections via `threading.local()`
- No locks needed

## Estimated Performance

| Metric | Before | After |
|--------|--------|-------|
| Cold request (45km) | 28s | 2-5s |
| Warm request (45km) | 10s | 1-3s |
| 100km route | **FAILS** | 3-6s |
| Memory usage | ~50MB peak/req | ~20MB steady + ~5MB/req |

## Deployment Plan

1. Deploy code changes (fallback ensures nothing breaks)
2. SSH into VPS, run: `docker compose exec backend python -m scripts.build_graph`
3. Verify via `/health` endpoint (graph_loaded: true)
4. Set up weekly cron: `0 3 * * 1` to refresh graph

## Verification

1. Docker build succeeds locally
2. Without graph files: routes still work via Overpass fallback
3. Run build script on VPS, verify `graph_data/` files created
4. With graph files: routes work faster, 100km routes succeed
5. `/health` shows graph metadata
6. Check backend logs for timing comparison
