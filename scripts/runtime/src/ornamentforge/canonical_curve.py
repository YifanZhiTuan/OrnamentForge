"""Version 1 editable Bezier payload; stdlib-only for host and Blender worker."""
import hashlib
import json
import math
import struct


def canonical_bytes(value: object) -> bytes:
    def normalize(v):
        if isinstance(v, dict):
            return {k: normalize(x) for k,x in v.items()}
        if isinstance(v, list):
            return [normalize(x) for x in v]
        if isinstance(v, float) and v.is_integer():
            return int(v)
        return v
    return json.dumps(normalize(value),sort_keys=True,separators=(",",":"),ensure_ascii=False,allow_nan=False).encode("utf-8")


def content_hash(payload: dict) -> str:
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()


def _keys(value, expected):
    if not isinstance(value,dict) or set(value) != set(expected):
        raise ValueError(f"Curve fields must be exactly {sorted(expected)}")


def _float(value):
    if type(value) not in (int,float) or not math.isfinite(value):
        raise ValueError("Curve coordinates must be finite numbers")
    value = struct.unpack("f",struct.pack("f",value))[0]
    if not math.isfinite(value):
        raise ValueError("Coordinate exceeds Blender float32 range")
    return value


def validate_curve(payload: dict) -> dict:
    _keys(payload,{"curve_version","representation","dimensions","resolution_u","twist_mode","cyclic","points"})
    if (payload["curve_version"] != "1.0" or payload["representation"] != "bezier_curve"
            or payload["dimensions"] != "3D" or payload["twist_mode"] != "Z_UP"):
        raise ValueError("Unsupported canonical curve settings")
    if type(payload["cyclic"]) is not bool or type(payload["resolution_u"]) is not int or not 1 <= payload["resolution_u"] <= 64:
        raise ValueError("Invalid curve resolution/cyclic flag")
    if not isinstance(payload["points"],list) or not 2 <= len(payload["points"]) <= 4096:
        raise ValueError("Invalid curve point count")
    result = json.loads(json.dumps(payload,allow_nan=False))
    for point in result["points"]:
        _keys(point,{"co","left","right","left_type","right_type","radius","tilt"})
        if point["left_type"] != "FREE" or point["right_type"] != "FREE":
            raise ValueError("V1 preserves explicit FREE Bezier handles only")
        for name in ("co","left","right"):
            if not isinstance(point[name],list) or len(point[name]) != 3:
                raise ValueError("Curve vectors require three coordinates")
            point[name] = [_float(v) for v in point[name]]
        point["radius"],point["tilt"] = _float(point["radius"]),_float(point["tilt"])
        if point["radius"] <= 0:
            raise ValueError("Curve radius must be positive")
    return result


def from_legacy(payload: dict) -> dict:
    _keys(payload,{"representation","cyclic","control_points"})
    if payload["representation"] != "bezier_curve":
        raise ValueError("Unsupported legacy representation")
    points = []
    for p in payload["control_points"]:
        _keys(p,{"co","left","right"})
        points.append({**p,"left_type":"FREE","right_type":"FREE","radius":1,"tilt":0})
    return validate_curve({"curve_version":"1.0","representation":"bezier_curve","dimensions":"3D",
                           "resolution_u":24,"twist_mode":"Z_UP","cyclic":payload["cyclic"],"points":points})


def control_points(payload: dict) -> list[dict]:
    return [{k:p[k] for k in ("co","left","right")} for p in payload["points"]]
