"""Focused eligibility/free-choice tests; no game source or history bias."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"web-author"))
from civilizations import _profile, eligible_rows, content_profile, selection_context

class CivilizationPolicyTests(unittest.TestCase):
    def rows(self):
        p=_profile()
        names=p["allowed_internal_names"]+[n for group in p["excluded_by_required_dlc"].values() for n in group]
        return [{"id":n,"name":n} for n in names]

    def test_standard_pool_includes_gifted_content_but_not_optional_dlc(self):
        rows=eligible_rows(self.rows());ids={r["id"] for r in rows}
        self.assertEqual(len(ids),42)
        self.assertTrue({"Bohemians","Poles","Burgundians","Sicilians","Bengalis","Dravidians","Gurjaras","Indians","Incas"}<=ids)
        self.assertFalse(ids & {"Romans","Armenians","Georgians","Jurchens","Khitans","Shu","Wei","Wu","Mapuche","Muisca","Tupi"})
        self.assertFalse(content_profile()["ownership_verified"])
        with self.assertRaises(ValueError):eligible_rows(self.rows()[1:])

    def test_ai_choice_exposes_full_pool_without_recommendations(self):
        rows=eligible_rows(self.rows())
        ctx=selection_context(rows,"new")
        self.assertEqual(len(ctx["eligible_ids"]),42)
        self.assertEqual(ctx["eligible_ids"],[row["id"] for row in rows])
        self.assertEqual(ctx["selection_method"],"free_choice_from_full_eligible_pool")
        self.assertNotIn("suggested",ctx)
        self.assertNotIn("history_scope",ctx)
        self.assertNotIn("observed_selections",ctx)
        self.assertTrue(any("自由选择" in item for item in ctx["choice_guidance"]))

    def test_history_and_project_identity_do_not_bias_choice_context(self):
        rows=eligible_rows(self.rows())
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            d=root/"old";d.mkdir()
            (d/"project.json").write_text(json.dumps({
                "project_id":"old",
                "request":{"civilization":"Britons"},
                "civilization_choice":{"selected_at":1}
            }))
            a=selection_context(rows,"project-a",root)
            b=selection_context(rows,"project-b",root)
            self.assertEqual(a["eligible_ids"],b["eligible_ids"])
            self.assertEqual(a["selection_method"],b["selection_method"])
            self.assertNotIn("suggested",a)
            self.assertNotIn("suggested",b)

if __name__=="__main__":unittest.main()
