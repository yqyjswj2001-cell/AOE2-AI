"""Developer UI copy and accessible control contracts."""
from html.parser import HTMLParser
from pathlib import Path
import unittest

WEB = Path(__file__).resolve().parents[3] / 'adjusted/web-author/web'


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.elements = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.elements.append((tag, dict(attrs)))


class ToolCopyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = (WEB / 'index.html').read_text(encoding='utf-8')
        cls.js = (WEB / 'app.js').read_text(encoding='utf-8')
        cls.css = (WEB / 'styles.css').read_text(encoding='utf-8')
        cls.elements = Elements(cls.html).elements

    def test_no_promotional_headings_or_hero(self):
        for phrase in ('你的打法', '你专注打法', '其余交给 Agent',
                       '怎样交锋', '你的风格', '正在成形', '已准备就绪',
                       '实际花了多少', '一起带回来', '准备好了',
                       'NEW CREATION', 'YOUR AGENT', 'YOUR CREATION'):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.html + self.js)
        for selector in ('authorization-hero', 'hero-insignia', 'hero-description'):
            self.assertNotIn(selector, self.html + self.css)

    def test_titles_name_functions(self):
        self.assertIn("const STEP_NAMES = ['Token 采集', '游戏模式', '文明选择', '参数设置', '生成结果'];", self.js)
        for label in ('脚本名', 'Token 用量', '开发报告'):
            self.assertIn(label, self.html)
        self.assertIn("label.textContent = 'Agent'", self.js)
        self.assertIn('.agent-select-field>label{display:block}', self.css)

    def test_consent_scope_and_failure_information_remain(self):
        for text in ('Token、模型、时间、会话 ID', '仅本项目', '可随时停止',
                     'usage 权限', '不保存聊天正文或密钥', '不发起模型调用',
                     '授权并继续', '本轮不计量', '停止采集'):
            self.assertIn(text, self.html)
        for element_id in ('errorNotice', 'usageGaps', 'usageCoverage', 'authorizationStatus'):
            self.assertTrue(any(attrs.get('id') == element_id for _, attrs in self.elements))

    def test_label_references_survive_heading_removal(self):
        ids = [attrs['id'] for _, attrs in self.elements if 'id' in attrs]
        self.assertEqual(len(ids), len(set(ids)))
        for _, attrs in self.elements:
            for key in ('aria-labelledby', 'aria-describedby'):
                for reference in attrs.get(key, '').split():
                    self.assertIn(reference, ids)
            if 'for' in attrs:
                self.assertIn(attrs['for'], ids)


if __name__ == '__main__':
    unittest.main()
