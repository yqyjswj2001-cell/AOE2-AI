# Reviewed line edits. Applied only to exact baseline files.
edit('adjusted/web-author/web/app.js', '0573cb29b7e6653c2ee7aae3a7d977eb24421c1747dbfb28460c0ff65b506c4f', 'db6d5b82ce970fe105bfb973ac45e319f9773809d7ead636ac47a81e7e698654', [
(20, 22, r'''  let lastUsage = null, reportBusy = false, resultView = 'progress';
  const STEP_NAMES = ['先连接，再创作。', '选择这轮对局。', '找到你的文明。', '定义你的打法。', '你的 AI，正在成形。'];
'''),
(117, 118, r'''    return authorizationReady() && authorizationConfirmed() && MODES.includes(value.mode) && (state?.civilizations || []).length > 0 &&
'''),
(158, 159, r'''      wizardStep = integer(draft.step) ? Math.min(draft.step, 3) : 0;
'''),
(178, 179, r'''    if (state && state.status !== 'configuring') return step === 4;
'''),
(187, 188, r'''    return false;
'''),
(191, 192, r'''    wizardStep = step;
    if (step === 3 && !$('scriptName').value) suggestName();
    saveDraft(); syncActions();
'''),
(202, 208, r'''      ['对局', MODE_NAMES[value.mode] || '尚未选择'],
      ['文明', value.civilization === 'auto' ? '由 AI 选择' : civ?.name || value.civilization || '尚未选择']
'''),
(220, 222, r'''    if ($('agent')) $('agent').disabled = !editable() || state?.usage_authorization?.authorized === true || !!state?.usage_authorization?.revoked_at;
    $('startButton').disabled = !editable() || wizardStep !== 3 || !validSelection(selection());
    $('startButton').classList.toggle('hidden', wizardStep !== 3 || !!locked);
    text('startButton', busy ? '正在提交…' : '开始生成 →');
'''),
(223, 227, r'''    text('settingsState', state?.status === 'configuring' ? (dirty ? '设置已保存在本机' : '本地创作') : state ? '本轮设置已固定' : '正在读取');
    text('startHint', !online ? '连接恢复后才能提交。' : '开始后固定本轮设置；AI 随即开始创作，不再二次确认。');
    text('configTitle', locked && state.status === 'completed' ? '你的 AI，已准备就绪。' : STEP_NAMES[wizardStep]);
    text('stepEyebrow', ['CONNECT', 'GAME MODE', 'CIVILIZATION', 'PLAY STYLE', 'YOUR CREATION'][wizardStep] + ' / 0' + (wizardStep + 1));
'''),
(236, 238, r'''    $('reviewBeforeStart').hidden = !!locked;
    $('authorForm').classList.toggle('hidden', !!finalRunning);
'''),
(239, 240, r'''    $('wizardActions').classList.toggle('hidden', !!finalRunning);
'''),
(241, 256, r'''    $('previousStep').disabled = busy || !online;
    $('nextStep').classList.toggle('hidden', wizardStep >= 3);
    $('nextStep').disabled = !editable() || (wizardStep === 0 ? !authorizationReady() : !canVisit(wizardStep + 1));
    text('nextStep', [authorizationConfirmed() ? '继续设置 →' : '授权并继续 →', '选择文明 →', '设置打法 →', '', ''][wizardStep]);
    $('skipMetering').classList.toggle('hidden', wizardStep !== 0 || authorizationConfirmed());
    $('skipMetering').disabled = !editable() || !agentsReady;
    text('navigationHint', locked ? '设置已固定，无需重复提交。' :
      wizardStep === 0 ? '不需要你选择或绑定会话。' :
      wizardStep === 1 ? '本轮不预设游戏模式。' :
      wizardStep === 2 ? (selectedCivValid() ? '文明已选定，可以继续。' : '选择一个文明，或交给 AI。') : '准备好了，就交给 AI。');
    document.querySelectorAll('[data-result]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.result === resultView)));
    ['progress', 'usage', 'report'].forEach(view => { $(view + 'Panel').hidden = resultView !== view; });
    renderMeterStatus(); renderSummary(); updateCivilizationSelection();
    $('generateReportButton').disabled = reportBusy || !online || !state || stopped;
    $('generateReportButton').setAttribute('aria-busy', String(reportBusy));
    text('generateReportButton', reportBusy ? '正在生成…' : '生成创作报告');
'''),
(257, 257, r'''  function renderMeterStatus() {
    const connection = state?.usage_connection || {};
    const labels = {NOT_AUTHORIZED:'等待授权', DISABLED:'本轮不计量', REVOKED:'计量已停止', RECORDING:'正在记录用量', LIMITED:'计量存在缺口', AWAITING_USAGE:'等待用量记录', CONNECTING:'Agent 正在接入'};
    text('meterStatus', labels[connection.status] || (state?.usage_authorization?.authorized ? 'Agent 正在接入' : '等待授权'));
    $('meterStatus').dataset.status = connection.status || 'NOT_AUTHORIZED';
    $('meterStatus').title = connection.reason || '这里只显示连接状态；完整数字在结果页。';
    $('revokeUsage').classList.toggle('hidden', connection.can_revoke !== true);
    $('revokeUsage').hidden = connection.can_revoke !== true;
    $('revokeUsage').disabled = busy || !online;
  }
  function suggestName() {
    if (!editable()) return;
    const names = ['Amber_Guard', 'Golden_Legion', 'Iron_Horizon', 'Dawn_Vanguard', 'Quiet_Storm', 'Silver_Banner'];
    const alternatives = names.filter(name => name !== $('scriptName').value);
    $('scriptName').value = alternatives[Math.floor(Math.random() * alternatives.length)];
    $('scriptName').setAttribute('aria-invalid', 'false');
    saveDraft();
  }
  function filterCivilizations() {
    const term = $('civilizationSearch').value.trim().toLocaleLowerCase();
    let visible = 0;
    document.querySelectorAll('.civilization-card').forEach(button => {
      const civ = civData(button.dataset.civilization);
      button.hidden = ![civ?.name, civ?.name_en, civ?.id].some(value => String(value || '').toLocaleLowerCase().includes(term));
      if (!button.hidden) visible++;
    });
    $('civilizationEmpty').classList.toggle('hidden', visible > 0 || !catalogReady);
  }

'''),
(367, 368, r'''    updateCivilizationSelection(); showCivilization($('civilization').value || state.civilizations[0]?.id); filterCivilizations();
'''),
(376, 377, r'''    const label = document.createElement('label'); label.htmlFor = 'agent'; label.textContent = '本次使用的 Agent';
'''),
(380, 381, r'''    const preferred = state?.usage_authorization?.agent || previous || state?.host_agent || 'auto';
    select.value = agents.some(agent => agent.id === preferred) ? preferred : agentsReady ? 'auto' : '';
'''),
(386, 396, r'''    let help = agent?.id === 'auto' ? '由正在运行的 Agent 确认身份和当前会话，无需手动绑定。' : '选择应与正在运行的工具一致；这里不会替你启动或切换 Agent。';
    if (agent?.id === 'cursor') help += state?.usage_access?.cursor_admin_configured
      ? ' 已配置 Team Usage API，实际数字以返回记录为准。'
      : ' 当前未配置 Team Usage API；没有 SDK 等真实来源时会明确显示缺口。';
    text('agentHelp', agent ? help : '正在读取可用的 Agent…');
    const auth = state?.usage_authorization;
    text('authorizationStatus', auth?.revoked_at ? '本轮授权已撤回；已记录数据保留，不再读取新用量。' :
      authorizationConfirmed() ? auth.authorized ? '已授权。后台已开始接入，读到数据后才会显示为正在记录。' : '本轮不计量。你仍然可以正常创作。' :
      '点击“授权并继续”才会开始读取；选择工具本身不代表已授权。');
'''),
(397, 397, r'''
'''),
(453, 453, r'''    applyUsageAuthorization(state.usage_authorization);
    text('progressTitle', state.status === 'completed' ? '作品文件已生成。' : state.status === 'invalid' ? '正在检查并修正参数。' : '正在创作你的 AI。');
'''),
(455, 456, r'''    text('fillCount', number(filled) + ' / ' + number(total) + ' 项参数');
    text('progressPercent', filled !== null && total !== null && filled <= total ? Math.floor(filled / total * 100) + '%' : '—');
'''),
(498, 500, r'''    const detail = state?.usage_connection?.reason || message;
    text('usageCapture', 'Agent：' + agentLabel + '。' + detail + ' 会话归属由 Agent 处理，无需你绑定。');
'''),
(508, 512, r'''    [['inputTokens','input_tokens'],['outputTokens','output_tokens'],['cacheTokens','cached_input_tokens'],
      ['cacheWriteTokens','cache_write_tokens'],['reasoningTokens','reasoning_tokens']].forEach(([id,key]) => text(id, finite(tokens[key]) ? number(tokens[key]) : '未提供'));
    text('usageBreakdown', '失败或取消的已知消耗 ' + number(tokens.failed_or_cancelled_tokens) +
      '；已标记重试 ' + number(tokens.retry_records) + ' 条，已知消耗 ' + number(tokens.retry_tokens) + '。这些消耗已包含在已记录总量中。');
'''),
(580, 583, r'''  async function authorize(allowed, advance = true) {
    if (!online || busy || stopped || !state || (!advance && !state.usage_authorization?.authorized)) return;
    if (advance && !editable()) return;
'''),
(585, 586, r'''      if (refreshPromise) await refreshPromise;
      const agent = state.usage_authorization?.authorized ? state.usage_authorization.agent : $('agent')?.value;
'''),
(587, 591, r'''        project_id:project, expected_revision:state.revision, agent, usage_authorized:allowed
      }), timeoutMs:30000});
      validateState(next); state = next;
      applyUsageAuthorization(next.usage_authorization);
      if (advance) wizardStep = 1;
      if (next.usage) renderUsage(next.usage);
'''),
(592, 593, r'''      const message = error.name === 'AbortError' ? '未收到授权回执，正在核对状态；不会重复开始创作。' : error.message;
'''),
(597, 597, r'''  }
  $('nextStep').addEventListener('click', () => {
    if (wizardStep !== 0) { goStep(wizardStep + 1); return; }
    if (authorizationConfirmed()) goStep(1);
    else authorize(true);
'''),
(598, 598, r'''  $('skipMetering').addEventListener('click', () => authorize(false));
  $('revokeUsage').addEventListener('click', () => authorize(false, false));
  $('suggestName').addEventListener('click', () => { suggestName(); syncActions(); });
  $('civilizationSearch').addEventListener('input', filterCivilizations);
  document.querySelectorAll('[data-result]').forEach(button => button.addEventListener('click', () => {
    resultView = button.dataset.result; syncActions();
  }));
'''),
(602, 603, r'''    const buttons = [...$('civilizationGrid').querySelectorAll('button:not([hidden])')], current = buttons.indexOf(document.activeElement);
'''),
(634, 637, r''''''),
(660, 661, r'''    if (wizardStep !== 3) return; // Enter in an earlier step must never grant consent or start creation.
'''),
(665, 666, r'''      if (refreshPromise) await refreshPromise;
      await api('/api/start', {method: 'POST', body: JSON.stringify({project_id:project, expected_revision: state.revision, ...value}), timeoutMs:30000});
'''),
(682, 683, r'''  setInterval(() => { if (!busy) refresh(); }, 3000);
'''),
])
