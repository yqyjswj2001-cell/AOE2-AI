from __future__ import annotations
import json
import shutil
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'adjusted/tools'))
import strategy_catalog as catalog_tool
import build_strategy_input as input_tool
from render_per_cloze import render_one, main as render_main

class StrategyClassificationTests(unittest.TestCase):
    def setUp(self):
        self.catalog=catalog_tool.load_catalog()

    def test_complete_partition_and_author_projection(self):
        rows=[r for profile in self.catalog['modules'].values() for r in profile['parameters']]
        self.assertEqual(len(rows),2295)
        self.assertEqual({r['decision'] for r in rows},{'fixed','dynamic'})
        catalog_tool.validate_author_cards(self.catalog,ROOT/'adjusted/cloze/strategy')
        for module,profile in self.catalog['modules'].items():
            cards=catalog_tool.make_author_cards(module,self.catalog)
            self.assertEqual({c['key'] for c in cards['parameters']},{r['key'] for r in profile['parameters'] if r['decision']=='dynamic'})
            for card in cards['parameters']:
                self.assertEqual(set(card),set(catalog_tool.AUTHOR_FIELDS))

    def test_author_contracts_expose_only_proven_mechanical_rules(self):
        contracts=catalog_tool.make_author_constraints(self.catalog)
        dynamic={r['key'] for p in self.catalog['modules'].values() for r in p['parameters'] if r['decision']=='dynamic'}
        fixed={r['key'] for p in self.catalog['modules'].values() for r in p['parameters'] if r['decision']=='fixed'}
        self.assertEqual(set(contracts['by_key']),dynamic)
        self.assertFalse(set(contracts['by_key']) & fixed)
        self.assertEqual(contracts['by_key']['ORB_ATTACK_GROUP_001']['zero_rule'],'forbidden')
        self.assertEqual(contracts['by_key']['ORB_ATTACK_GROUP_003']['zero_rule'],'allowed_by_static_rule')
        self.assertTrue(all(not (set(c['keys']) & fixed) for c in contracts['constraints']))

    def test_fixed_value_cannot_be_reopened_even_with_a_renamed_key(self):
        for module,profile in self.catalog['modules'].items():
            fixed=next((r for r in profile['parameters'] if r['decision']=='fixed'),None)
            if fixed is None:
                continue
            source=(ROOT/'official/raw/Promisory'/module).read_bytes().decode('utf-8')
            good=catalog_tool.expected_template(module,source,self.catalog)
            shift=sum(len('{{'+r['key']+'}}')-(r['source_end']-r['source_start']) for r in profile['parameters'] if r['decision']=='dynamic' and r['source_start']<fixed['source_start'])
            start=fixed['source_start']+shift
            end=fixed['source_end']+shift
            bad=good[:start]+'{{RENAMED_UNAPPROVED}}'+good[end:]
            with self.subTest(module=module):
                with self.assertRaises(catalog_tool.BoundaryError):
                    catalog_tool.validate_classified_template(module,source,bad,self.catalog)
            return
        self.fail('no fixed parameter in complete classification')

    def test_fully_fixed_module_requires_no_author_answer_file(self):
        module=next(name for name,p in self.catalog['modules'].items() if not any(r['decision']=='dynamic' for r in p['parameters']))
        with tempfile.TemporaryDirectory() as td:
            actual=render_one(ROOT/'adjusted/cloze/Promisory'/(module+'.tpl'),Path(td)/'missing.json',ROOT/'adjusted/cloze/official-defaults'/(module.removesuffix('.per')+'.json'))
            self.assertEqual(actual.encode('utf-8'),(ROOT/'official/raw/Promisory'/module).read_bytes())

    def test_author_package_contains_no_templates_defaults_or_fixed_parameters(self):
        self.assertTrue(input_tool.facts.FACTS_ROOT.is_dir(), "required frozen facts are missing from adjusted/knowledge/facts")
        for name in input_tool.facts.FILES:
            self.assertTrue((input_tool.facts.FACTS_ROOT / name).is_file(), "required frozen fact is missing: " + name)
        with tempfile.TemporaryDirectory() as td:
            out=Path(td)/'author'
            result=input_tool.build(out)
            self.assertTrue(result['ok'])
            manifest=json.loads((out/'manifest.json').read_text(encoding='utf-8'))
            self.assertFalse(manifest['fixed_source_included'])
            self.assertFalse(manifest['official_answers_included'])
            contracts=json.loads((out/'PARAMETER_CONSTRAINTS.json').read_text(encoding='utf-8'))
            self.assertEqual(set(contracts['by_key']),{
                r['key'] for p in self.catalog['modules'].values() for r in p['parameters'] if r['decision']=='dynamic'})
            for p in out.rglob('*'):
                if p.is_file():
                    self.assertNotIn(p.suffix,{'.per','.ai','.tpl','.xs'})
                    self.assertNotIn('official-defaults',p.parts)
                    self.assertNotIn('classification',p.parts)
            expected={r['key'] for p in self.catalog['modules'].values() for r in p['parameters'] if r['decision']=='dynamic'}
            actual=set()
            for p in (out/'answers').glob('*.json'):
                answers=json.loads(p.read_text(encoding='utf-8'))
                self.assertTrue(all(value is None for value in answers.values()))
                actual.update(answers)
            self.assertEqual(actual,expected)
            with self.assertRaises(catalog_tool.BoundaryError):
                input_tool.build(out)

    def test_missing_module_cannot_hide_an_unanswered_module(self):
        with tempfile.TemporaryDirectory() as td:
            tmp=Path(td)
            templates=tmp/'templates'; templates.mkdir()
            only=next((ROOT/'adjusted/cloze/Promisory').glob('*.per.tpl'))
            shutil.copy2(only,templates/only.name)
            out=tmp/'out'
            self.assertEqual(render_main(['--templates',str(templates),'--answers-dir',str(tmp/'answers'),'--out',str(out)]),2)
            self.assertFalse(out.exists())

    def test_author_prose_rejects_other_per_commands_and_reference_answers(self):
        for text in ('(train archer)', '(up-modify-sn sn-target-player-number c:= 2)', '(load "private")', '默认值为42'):
            with self.subTest(text=text):
                with self.assertRaises(catalog_tool.BoundaryError):
                    catalog_tool.validate_author_prose(text,'fixture')
        catalog_tool.validate_author_prose('选择资源份额，四项合计100。','fixture')

    def test_percentage_and_building_domains_do_not_allow_negative_choices(self):
        constraint=next(c for c in self.catalog['constraints'] if c['kind']=='sum_equal' and all(any(r['key']==key and r['decision']=='dynamic' for p in self.catalog['modules'].values() for r in p['parameters']) for key in c['keys']))
        module=constraint['module']
        values={r['key']:r['official_value'] for r in self.catalog['modules'][module]['parameters'] if r['decision']=='dynamic'}
        first,second=constraint['keys'][:2]
        values[second]+=values[first]+1
        values[first]=-1
        self.assertEqual(sum(values[k] for k in constraint['keys']),constraint['value'])
        with self.assertRaises(catalog_tool.BoundaryError):
            catalog_tool.validate_classified_answers(module,values,self.catalog)
        module=next(name for name,p in self.catalog['modules'].items() if any(r['decision']=='dynamic' and r['unit']=='座' for r in p['parameters']))
        rows=self.catalog['modules'][module]['parameters']
        values={r['key']:r['official_value'] for r in rows if r['decision']=='dynamic'}
        values[next(r['key'] for r in rows if r['decision']=='dynamic' and r['unit']=='座')]=-1
        with self.assertRaises(catalog_tool.BoundaryError):
            catalog_tool.validate_classified_answers(module,values,self.catalog)

if __name__=='__main__':
    unittest.main()
