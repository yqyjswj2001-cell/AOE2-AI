# Reviewed line edits. Applied only to exact baseline files.
edit('adjusted/tests/web_author/test_installable_ai.py', '08cd70738bbd38b24fe3d477da46e4c622a82df32c966a6591822e4cdf4659a0', '8966271bfe52feef292ee6c1a148ce7f7657ca0d634dca4324db26cd0d5b1b31', [
(28, 29, r'''        for index in range(10):
'''),
(37, 38, r'''            '; official loader fixture\n' + ''.join(f'(load "Promisory\\module{i}")\n' for i in range(2, 10)),
'''),
(52, 54, r'''        self.assertEqual(result["loaded_modules"], [f"module{i}.per" for i in range(10)])
        self.assertEqual(len(result["unreferenced_modules"]), 26)
'''),
])
edit('adjusted/tests/web_author/test_wizard_contract.py', 'edb43f790f975b88736bbcc5ce6477da24e893b364a7ddcd1345579f70f90d41', '95beae35b8a7a7f5ff8a9c98e769bdcaf614f4be1a8f8577abf667851525737e', [
(64, 65, r'''  self.assertIn("$('authorForm').classList.toggle('hidden', !!finalRunning)",js)
'''),
(71, 72, r'''  self.assertIn('<span>01</span><span class="step-copy">授权',html)
'''),
(73, 74, r'''  self.assertIn('授权并继续',html)
'''),
])
