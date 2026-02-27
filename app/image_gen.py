# app/image_gen.py
"""Route image generation using Cairo (1080x1080 PNG for Strava sharing)."""

import io
import math

import cairo

from .wind_utils import degrees_to_cardinal, wind_arrow_rotation

_W = 1080
_H = 1080
_PAD = 52
_HEADER_H = 72
_STATS_H = 128
_MAP_H = 720
_JUNC_H = 100


def _hex_to_rgb(hex_color: str) -> tuple[float, float, float]:
    """Convert hex color like '#06b6d4' to (r, g, b) floats 0-1."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return (r, g, b)


def _set_color(ctx: cairo.Context, hex_color: str, alpha: float = 1.0) -> None:
    r, g, b = _hex_to_rgb(hex_color)
    if alpha < 1.0:
        ctx.set_source_rgba(r, g, b, alpha)
    else:
        ctx.set_source_rgb(r, g, b)


def _draw_text(ctx: cairo.Context, text: str, x: float, y: float,
               size: float = 13, bold: bool = False, color: str = "#f1f5f9",
               align: str = "left") -> float:
    """Draw text and return its width. y is baseline."""
    weight = cairo.FONT_WEIGHT_BOLD if bold else cairo.FONT_WEIGHT_NORMAL
    ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, weight)
    ctx.set_font_size(size)
    _set_color(ctx, color)
    extents = ctx.text_extents(text)
    if align == "right":
        x = x - extents.width
    elif align == "center":
        x = x - extents.width / 2
    ctx.move_to(x, y)
    ctx.show_text(text)
    return extents.width


def generate_image(route_data: dict, wind_data: dict) -> bytes:
    """Generate a 1080x1080 PNG route image.

    Args:
        route_data: Dict with keys: start_address, actual_distance_km,
            junctions, junction_coords, route_geometry.
        wind_data: Dict with keys: speed, direction.

    Returns:
        PNG image as bytes.
    """
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, _W, _H)
    ctx = cairo.Context(surface)

    # Background
    _set_color(ctx, "#030712")
    ctx.rectangle(0, 0, _W, _H)
    ctx.fill()

    # --- Header ---
    _set_color(ctx, "#0c1220")
    ctx.rectangle(0, 0, _W, _HEADER_H)
    ctx.fill()
    _set_color(ctx, "#1e293b")
    ctx.rectangle(0, _HEADER_H, _W, 1)
    ctx.fill()

    rgwnd_w = _draw_text(ctx, "RGWND", _PAD, _HEADER_H / 2 + 12,
                         size=32, bold=True, color="#06b6d4")
    _draw_text(ctx, ".app", _PAD + rgwnd_w, _HEADER_H / 2 + 12,
               size=32, color="#334155")

    # --- Stats row ---
    stats_y = _HEADER_H + 1
    mid_x = _W / 2

    # Divider
    _set_color(ctx, "#1e293b")
    ctx.rectangle(mid_x, stats_y + 16, 1, _STATS_H - 32)
    ctx.fill()

    # Distance (left)
    dist_str = str(route_data["actual_distance_km"])
    dist_w = _draw_text(ctx, dist_str, _PAD, stats_y + 92,
                        size=72, bold=True, color="#f1f5f9")
    _draw_text(ctx, " km", _PAD + dist_w, stats_y + 92,
               size=28, bold=True, color="#334155")
    _draw_text(ctx, "AFSTAND", _PAD, stats_y + 114,
               size=12, color="#475569")

    # Wind (right)
    wind_kmh = f"{wind_data['speed'] * 3.6:.1f}"
    wind_dir = degrees_to_cardinal(wind_data["direction"])
    wind_x = mid_x + _PAD

    w_w = _draw_text(ctx, wind_kmh, wind_x, stats_y + 60,
                     size=44, bold=True, color="#f1f5f9")
    _draw_text(ctx, " km/h", wind_x + w_w, stats_y + 60,
               size=20, color="#475569")
    _draw_text(ctx, wind_dir, wind_x, stats_y + 95,
               size=28, bold=True, color="#06b6d4")
    _draw_text(ctx, "WIND", wind_x, stats_y + 114,
               size=12, color="#475569")

    # Wind arrow
    arrow_rot = wind_arrow_rotation(wind_data["direction"])
    ctx.save()
    ctx.translate(_W - _PAD - 20, stats_y + 64)
    ctx.rotate(arrow_rot * math.pi / 180)
    _set_color(ctx, "#06b6d4")
    ctx.move_to(0, -20)
    ctx.line_to(14, 0)
    ctx.line_to(4, 0)
    ctx.line_to(4, 16)
    ctx.line_to(-4, 16)
    ctx.line_to(-4, 0)
    ctx.line_to(-14, 0)
    ctx.close_path()
    ctx.fill()
    ctx.restore()

    # Separator
    _set_color(ctx, "#1e293b")
    ctx.rectangle(0, stats_y + _STATS_H, _W, 1)
    ctx.fill()

    # --- Route sketch ---
    map_y = stats_y + _STATS_H + 1

    all_points = [p for seg in route_data["route_geometry"] for p in seg]
    if len(all_points) > 1:
        lats = [p[0] for p in all_points]
        lons = [p[1] for p in all_points]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        cos_lat = math.cos((min_lat + max_lat) / 2 * math.pi / 180)
        norm_lon_range = (max_lon - min_lon) * cos_lat or 0.01
        norm_lat_range = max_lat - min_lat or 0.01

        draw_pad = 56
        avail_w = _W - draw_pad * 2
        avail_h = _MAP_H - draw_pad * 2

        scale = min(avail_w / norm_lon_range, avail_h / norm_lat_range) * 0.88
        drawn_w = norm_lon_range * scale
        drawn_h = norm_lat_range * scale
        offset_x = draw_pad + (avail_w - drawn_w) / 2
        offset_y = map_y + draw_pad + (avail_h - drawn_h) / 2

        def to_x(lon: float) -> float:
            return offset_x + (lon - min_lon) * cos_lat * scale

        def to_y(lat: float) -> float:
            return offset_y + (max_lat - lat) * scale

        # Route line
        _set_color(ctx, "#06b6d4")
        ctx.set_line_width(3)
        ctx.set_line_join(cairo.LINE_JOIN_ROUND)
        ctx.set_line_cap(cairo.LINE_CAP_ROUND)

        for segment in route_data["route_geometry"]:
            if len(segment) < 2:
                continue
            ctx.move_to(to_x(segment[0][1]), to_y(segment[0][0]))
            for lat, lon in segment[1:]:
                ctx.line_to(to_x(lon), to_y(lat))
            ctx.stroke()

        # Junction dots
        for jc in route_data["junction_coords"]:
            cx = to_x(jc["lon"])
            cy = to_y(jc["lat"])
            _set_color(ctx, "#030712")
            ctx.arc(cx, cy, 6, 0, math.pi * 2)
            ctx.fill()
            _set_color(ctx, "#e2e8f0")
            ctx.set_line_width(2)
            ctx.arc(cx, cy, 6, 0, math.pi * 2)
            ctx.stroke()

    # --- Junctions strip ---
    junc_y = map_y + _MAP_H
    _set_color(ctx, "#0c1220")
    ctx.rectangle(0, junc_y, _W, _JUNC_H)
    ctx.fill()
    _set_color(ctx, "#1e293b")
    ctx.rectangle(0, junc_y, _W, 1)
    ctx.fill()

    _set_color(ctx, "#06b6d4")
    ctx.rectangle(_PAD, junc_y + 18, 3, _JUNC_H - 36)
    ctx.fill()

    _draw_text(ctx, "ROUTE", _PAD + 14, junc_y + 36,
               size=11, color="#475569")

    junction_str = " → ".join(route_data["junctions"])
    # Word wrap
    ctx.select_font_face("sans-serif", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
    ctx.set_font_size(18)
    max_jw = _W - _PAD * 2 - 14
    words = junction_str.split(" ")
    line = ""
    jy = junc_y + 62
    _set_color(ctx, "#67e8f9")
    for word in words:
        test = f"{line} {word}" if line else word
        if ctx.text_extents(test).width > max_jw and line:
            ctx.move_to(_PAD + 14, jy)
            ctx.show_text(line)
            line = word
            jy += 24
        else:
            line = test
    if line:
        ctx.move_to(_PAD + 14, jy)
        ctx.show_text(line)

    # --- Footer ---
    foot_y = junc_y + _JUNC_H
    _set_color(ctx, "#1e293b")
    ctx.rectangle(0, foot_y, _W, 1)
    ctx.fill()

    _draw_text(ctx, "Wind-geoptimaliseerde fietsroutes · België",
               _PAD, foot_y + 38, size=13, color="#334155")
    _draw_text(ctx, "rgwnd.app", _W - _PAD, foot_y + 38,
               size=13, bold=True, color="#06b6d4", align="right")

    # Export to PNG bytes
    buf = io.BytesIO()
    surface.write_to_png(buf)
    buf.seek(0)
    return buf.read()
