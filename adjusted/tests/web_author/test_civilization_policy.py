"""Focused eligibility/recommendation tests; metadata only, no game source."""
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
    def test_less_used_recommendations_leave_all_civilizations_eligible(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            for i in range(10):
                d=root/str(i);d.mkdir()
                (d/"project.json").write_text(json.dumps({"project_id":str(i),"request":{"civilization":"Britons" if i<8 else "Byzantines"},"civilization_choice":{"selected_at":i+1}}))
            rows=eligible_rows(self.rows())
            ctx=selection_context(rows,"new",root)
            self.assertEqual(ctx["observed_selections"],10)
            self.assertEqual(len(ctx["suggested"]),6)
            self.assertFalse({"Britons","Byzantines"}&{x["id"] for x in ctx["suggested"]})
            self.assertTrue({"Britons","Byzantines"}<=set(ctx["eligible_ids"]))
            self.assertEqual(ctx,selection_context(rows,"new",root))
    def test_empty_history_is_not_a_claim_about_actual_games(self):
        with tempfile.TemporaryDirectory() as tmp:
            rows=eligible_rows(self.rows())
            a=selection_context(rows,"project-a",Path(tmp))
            b=selection_context(rows,"project-b",Path(tmp))
            self.assertEqual(a["observed_selections"],0)
            self.assertNotEqual(a["suggested"],b["suggested"])
            self.assertIn("不是游戏出场率",a["history_scope"])
if __name__=="__main__":unittest.main()
