# Optimized Route Calculation — DFS Loop Finder

## Context

After the pre-computed graph plan (PRECOMPUTED_GRAPH_PLAN.md), the DFS loop finder in `app/routing.py:102-176` becomes the new main bottleneck. Currently it takes 2-30s and hits the 30s time limit on dense areas. Root cause: iterative DFS creates a new `frozenset` and `list` on every stack push — millions of Python allocations. Two phases: pure Python first (immediate ~4x), Rust second (additional ~20x).

## Phase 1: Pure Python Recursive Backtracking

### Modified: `app/routing.py`

Replace `_find_knooppunt_loops` (lines 102-176) entirely. Signature and return value stay identical.

**Key changes:**
1. **Recursive DFS with backtracking** — shared mutable `set` + `list`, `add`/`remove` instead of `frozenset | {n}` and `path + [n]` on every push. `path[:]` copy only happens when a valid loop is found (rare).
2. **Pre-built adjacency list** — `adj_list: dict[int, list[tuple[int, float]]]` built once before DFS. Avoids `K.edges[u,v]["length"]` dict lookups in hot loop.
3. **Pre-computed distances to start** — `dist_to_start: dict[int, float]` built once with haversine. Replaces haversine call on every neighbor check with O(1) dict lookup.
4. **Pruning order** — cheapest checks first: `in visited` → `> max_dist` → `>= max_depth` → `dist_to_start` pruning.
5. **Time limit via counter list** — `counter = [0]` passed by reference through closure; checked every 10K iterations.

```python
def _find_knooppunt_loops(K, start_kp, target_m, tolerance, max_depth=15, time_limit=30.0):
    min_dist = target_m * (1 - tolerance)
    max_dist = target_m * (1 + tolerance)
    candidates = []
    t_start = time.perf_counter()

    avg_degree = 2 * K.number_of_edges() / max(K.number_of_nodes(), 1)
    if avg_degree > 10: max_depth = min(max_depth, 10)
    elif avg_degree > 6: max_depth = min(max_depth, 12)

    # Pre-build adjacency list (tuples, no dict lookups in inner loop)
    adj_list = {n: [] for n in K.nodes()}
    for u, v, data in K.edges(data=True):
        adj_list[u].append((v, data["length"]))
        adj_list[v].append((u, data["length"]))

    # Pre-compute distances to start (replaces haversine in inner loop)
    s_lat, s_lon = K.nodes[start_kp]["y"], K.nodes[start_kp]["x"]
    dist_to_start = {n: overpass._haversine(K.nodes[n]["y"], K.nodes[n]["x"], s_lat, s_lon)
                     for n in K.nodes()}

    counter = [0]

    def _dfs(node, visited, path, dist):
        counter[0] += 1
        if counter[0] % 10000 == 0 and time.perf_counter() - t_start > time_limit:
            return True

        for neighbor, edge_len in adj_list[node]:
            new_dist = dist + edge_len
            if neighbor == start_kp:
                if len(path) >= 3 and min_dist <= new_dist <= max_dist:
                    candidates.append((path[:] + [start_kp], new_dist))
                    if len(candidates) >= 500: return True
                continue
            if neighbor in visited: continue
            if new_dist > max_dist: continue
            if len(path) >= max_depth: continue
            if new_dist + dist_to_start[neighbor] * 0.7 > max_dist: continue
            visited.add(neighbor); path.append(neighbor)
            if _dfs(neighbor, visited, path, new_dist): return True
            path.pop(); visited.remove(neighbor)
        return False

    _dfs(start_kp, {start_kp}, [start_kp], 0.0)
    return candidates
```

No other changes needed. `find_wind_optimized_loop`, `_score_loop`, `_add_knooppunt_effort`, etc. all stay the same.

## Phase 2: Rust DFS via PyO3

### New: `rust_routing/` directory

```
rust_routing/
    Cargo.toml
    pyproject.toml
    src/lib.rs
```

**`Cargo.toml`:**
```toml
[package]
name = "rust_routing"
version = "0.1.0"
edition = "2021"
[lib]
name = "rust_routing"
crate-type = ["cdylib"]
[dependencies]
pyo3 = { version = "0.21", features = ["extension-module"] }
[profile.release]
opt-level = 3
lto = true
codegen-units = 1
```

**`pyproject.toml`:**
```toml
[build-system]
requires = ["maturin>=1.5,<2.0"]
build-backend = "maturin"
[project]
name = "rust_routing"
requires-python = ">=3.12"
[tool.maturin]
features = ["pyo3/extension-module"]
```

**`src/lib.rs`** — `find_loops_rust(adj, dist_to_start, start, min_dist, max_dist, max_depth, time_limit_secs) -> Vec<(Vec<i64>, f64)>`. Same algorithm as Phase 1 but in Rust: `HashSet<i64>`, `Vec<i64>` backtracking, check `Instant::now() >= deadline` every 100K iterations (Rust is ~20x faster so check less often), clone path only on valid loop.

### Modified: `Dockerfile`

Add multi-stage build before the Python stage:

```dockerfile
FROM ghcr.io/pyo3/maturin:latest AS rust-builder
WORKDIR /build/rust_routing
COPY rust_routing/ .
RUN maturin build --release --out /build/dist

FROM python:3.12-slim
# ... existing setup ...
COPY --from=rust-builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl
# ... rest unchanged ...
```

### Modified: `app/routing.py`

Add at top (after existing imports):
```python
try:
    from rust_routing import find_loops_rust as _find_loops_rust_native
    _RUST_AVAILABLE = True
except ImportError:
    _RUST_AVAILABLE = False
```

Inside `_find_knooppunt_loops`, after pre-computation, before Python DFS:
```python
if _RUST_AVAILABLE:
    try:
        return _find_loops_rust_native(adj_list, dist_to_start, start_kp,
                                       min_dist, max_dist, max_depth, time_limit)
    except Exception as e:
        logger.warning("Rust DFS mislukt (%s), Python fallback", e)
# ... Python recursive DFS below ...
```

## Performance

| Scenario | Current | Phase 1 | Phase 2 |
|---------|---------|---------|---------|
| 45km typical | 2-10s | 0.5-2.5s | <0.5s |
| Dense area (was timeout) | TIMEOUT | 7-10s | <2s |
| Docker build (first) | 30s | 30s | ~3min |
| Docker build (code-only) | 30s | 30s | ~30s |

## Implementation Sequence

1. **Phase 1 first**: Edit `routing.py`, build Docker, test, deploy
2. Check `timings.loop_finding_algorithm` in API response — should drop to <3s
3. **Phase 2**: Create `rust_routing/`, update `Dockerfile`, verify "Rust DFS module geladen" in logs
4. Deploy to VPS

## Files

- `app/routing.py` — replace `_find_knooppunt_loops` lines 102-176 + add Rust call path
- `Dockerfile` — add `rust-builder` stage
- `rust_routing/Cargo.toml`, `rust_routing/pyproject.toml`, `rust_routing/src/lib.rs` — new
