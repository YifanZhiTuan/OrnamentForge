"""B01 measured stage gates. Evaluated geometry is the source of measurements."""
from .blender_contract import numeric_metric
from .qa import MandatoryCheck, Metric, QAReport


def assess_b01(plan: dict, metrics: dict, stage: int) -> QAReport:
    checks, values = [], []
    p, tolerance = plan["parameters"], plan["tolerance"]
    def check(name, value, passed, threshold=None):
        checks.append(MandatoryCheck(name, bool(passed), "Measured from Blender evaluated geometry"))
        if type(value) in (int,float):
            values.append(Metric(name, value, threshold, "World units; evaluated mesh or object count"))
    if stage >= 2:
        error = numeric_metric(metrics,"base_dimension_error")
        check("base_dimensions",error,error <= tolerance,tolerance)
    if stage >= 3:
        motifs = metrics["motif_validation"]
        valid = set(motifs) == {"B01_Vine","B01_LeafTemplate"} and all(
            m["editable_curve"] is True and m["vertices"] > 0 and
            numeric_metric(m,"stroke_width") + tolerance >= plan["minimum_feature_width"] for m in motifs.values())
        check("motif_validation",None,valid)
    if stage >= 4:
        for name, threshold, relation in (
            ("margin_clearance",p["margin"],"min"),
            ("attachment_gap",plan["attachment_distance"],"max"),
            ("burial_depth",plan["burial_threshold"],"max"),
            ("minimum_feature_width",plan["minimum_feature_width"],"min")):
            value = numeric_metric(metrics,name)
            passed = value+tolerance >= threshold if relation == "min" else value <= threshold
            check(name,value,passed,threshold)
        count = numeric_metric(metrics,"leaf_count")
        check("leaf_count",count,count == p["leaf_count"],p["leaf_count"])
        expected = {"B01_Base","B01_Vine","B01_LeafTemplate"} | {t["name"] for t in plan["leaf_transforms"]}
        actual = set(metrics["object_names"])
        check("expected_objects",None,expected <= actual)
    if stage >= 6:
        for name in ("emboss_height","emboss_height_min"):
            value = numeric_metric(metrics,name)
            check(name,value,abs(value-p["emboss_height"]) <= tolerance,p["emboss_height"])
    return QAReport(geometry_metrics=values,mandatory_checks=checks,
                    final_pass=all(c.passed for c in checks) if checks else None,
                    notes=f"B01 G{stage} measured gate; visual metrics unassessed; editable output only")
