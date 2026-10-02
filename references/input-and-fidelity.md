# Input and Fidelity

Use the launcher prefix from setup.md. Save user inputs under the external workspace.

## Reference

```text
... run.py --workspace <WORKSPACE> cli route --reference inputs/reference.png --output runs/current/intake.json
```

Use `--reference-mode line_art|color_block|mixed` only when classification needs an
explicit override. Preserve original and SHA256. No AI redesign without an explicit
request. Allowed edits must keep original/edited files, hashes and operation evidence.
Single flat raster only; multiple references and arbitrary mesh input are unsupported.
Exit codes: READY 0, HOLD 2, NOT_SUPPORTED 3. Failure master is null.

For line-art diagnostics and a normalized mask:

```text
... run.py --workspace <WORKSPACE> module ornamentforge.current.fidelity.line_art_pass --source inputs/reference.png --output runs/current/lineart
```

The output must be new/empty. Outputs include binary_mask.png (WHITE=stroke),
skeleton.png, stroke_graph.json, planar_master.json, qa.json, fidelity_preview.png
and comparison.png. A HOLD master is diagnostic-only. Check actual motif identity,
missing silhouettes/petals, broken tails, incorrect merges and noise regions.
Do not treat image recall as sufficient topology QA. Dense field engraving can
use a reviewed mask even when vector junction metrics HOLD; document that separate
route decision. A damaged mask/source cannot be passed through this exception.

## Prompt-only AI design

Use only the session's real image generation/editing tool, following its applicable
tool instructions and imagegen skill if available. No Python image provider, API
keys or fallback sources. If the current session has no callable Codex image tool,
return `AI_IMAGE_TOOL_UNAVAILABLE / HOLD` immediately; do not create a substitute. Generate 2–4 candidates; if one output per call, call
sequentially. Save actual PNGs, tool receipts, exact prompts and timestamps in a
new `runs/current/ai_design/<run_id>/`. Never label a fixture as tool output.

Prompt template: original traditional ornament matching the requested subjects and
composition; frontal orthographic flat 2D master; white/warm ivory background;
clean dark contours, coherent hierarchy, flowing curves and controlled negative
space; no vessel, perspective, scene, shadows, lighting/material simulation, text,
watermark, modern logo or cartoon. Engraving emphasizes lines, relief fuller
enclosed masses, painted bounded flat regions. Preserve requested complexity.

Visually score identity, silhouette, hierarchy, flow, negative space, traditional
ornament feeling and extraction friendliness (1–5). Record observations and reason
for selection. At most two repair rounds, then HOLD. Copy the selected PNG unchanged
to selected_reference.png. Tool declaration is not cryptographic generation proof.

```python
from pathlib import Path
from ornamentforge.current.design import DesignHandoff
run = Path("runs/current/ai_design/my_design")
# Execute only after actual tool outputs exist and have been reviewed.
record = DesignHandoff.create(
    original_user_prompt=user_prompt, design_prompt=exact_prompt_sent,
    candidates={"A": run / "candidate_A.png", "B": run / "candidate_B.png"},
    selected_candidate=chosen_id, generator="codex_image_tool",
    selection_notes=actual_review,
    provenance={"tool_evidence": retained_receipt},
)
record.save(run / "design_handoff.json")
```

```text
... cli route --reference runs/current/ai_design/my_design/selected_reference.png --design-handoff runs/current/ai_design/my_design/design_handoff.json --output runs/current/ai_design/my_design/intake.json
```

All candidates and selected file must pass handoff hash verification. Output is the
same Fidelity → PlanarMasterV1 contract, still requiring visual review.

