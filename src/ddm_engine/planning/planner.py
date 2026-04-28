from __future__ import annotations

from ddm_engine.extraction.models import BoundingBox, DocumentLayout
from ddm_engine.planning.models import RedactionDecision, RedactionPlan, RedactionRegion


class RedactionPlanner:
    def __init__(self, box_padding: float = 1.5) -> None:
        self.box_padding = box_padding

    def plan(
        self,
        job_id: str,
        decisions: list[RedactionDecision],
        layout: DocumentLayout,
    ) -> RedactionPlan:
        page_sizes = {page.page_number: (page.width, page.height) for page in layout.pages}
        regions: list[RedactionRegion] = []

        for decision in decisions:
            page_width, page_height = page_sizes.get(decision.page_number, (None, None))
            for box_index, box in enumerate(decision.boxes, start=1):
                regions.append(
                    RedactionRegion(
                        region_id=f"{decision.decision_id}-region-{box_index}",
                        decision_id=decision.decision_id,
                        label=decision.label,
                        page_number=decision.page_number,
                        bbox=_padded_box(box, self.box_padding, page_width, page_height),
                        source_candidate_ids=decision.source_candidate_ids,
                    )
                )

        return RedactionPlan(job_id=job_id, decisions=decisions, regions=regions)


def _padded_box(
    box: BoundingBox,
    padding: float,
    page_width: float | None,
    page_height: float | None,
) -> BoundingBox:
    x0 = max(0.0, box.x0 - padding)
    y0 = max(0.0, box.y0 - padding)
    x1 = box.x1 + padding
    y1 = box.y1 + padding
    if page_width is not None:
        x1 = min(page_width, x1)
    if page_height is not None:
        y1 = min(page_height, y1)
    return BoundingBox(x0=x0, y0=y0, x1=x1, y1=y1)
