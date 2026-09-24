/* Local author UI, adapted from AoE2 AI Studio. Server state is authoritative. */
'use strict';
(() => {
  const $ = id => document.getElementById(id);
  const AGES = ['dark', 'feudal', 'castle', 'imperial'];
  const MODES = ['1v1', '2v2', '3v3', '4v4', 'ffa4', 'ffa8'];
  const OUTPUT_MODES = ['raw_scripts', 'share_package'];
  const DRAFT_SCHEMA = 'aoe2-parameter-web-draft-v4';
  const STATUS = {
    configuring: ['待配置', ''],
    selecting: ['选择文明', '正在选择文明。'],
    authoring: ['生成中', '正在生成参数。'],
    invalid: ['检查中', '发现需要修正的参数。'],
    ready: ['准备文件', '检查通过，准备生成文件。'],
    rendering: ['生成文件', '正在生成文件。'],
    completed: ['已完成', '脚本已生成。']
  };
  let state = null, online = false, busy = false, refreshPromise = null, stopped = false;
  let project = null, draftLoaded = false, storageAvailable = true, dirty = false, networkError = false;
  let lastRequestSignature = null, civilizationSignature = null, agentSignature = null;
  let wizardStep = 0, previewCivilization = null, catalog = [], agents = [], catalogReady = false, agentsReady = false;
  let lastUsage = null, reportBusy = false, resultView = 'progress';
  const STEP_NAMES = ['Token 采集', '游戏模式', '文明选择', '参数设置', '生成结果'];
  const MODE_NAMES = {'1v1':'1v1 单挑','2v2':'2v2 团队战','3v3':'3v3 团队战','4v4':'4v4 团队战',ffa4:'4 人混战',ffa8:'8 人混战'};
  const finite = value => typeof value === 'number' && Number.isFinite(value);
  const integer = value => Number.isInteger(value) && value >= 0;
  const number = value => finite(value) ? new Intl.NumberFormat('zh-CN').format(value) : '未采集';
  const duration = value => {
    if (!finite(value) || value < 0) return '等待记录';
    const seconds = Math.floor(value), h = Math.floor(seconds / 3600), m = Math.floor(seconds % 3600 / 60);
    return (h ? h + '时 ' : '') + m + '分 ' + seconds % 60 + '秒';
  };
  const text = (id, value) => { $(id).textContent = value; };
  function developerKey() { return project ? 'aoe2.web-author.developer.' + project : null; }
  function developerObservations() {
    const key = developerKey();
    if (!key) return [];
    try {
      const value = JSON.parse(localStorage.getItem(key) || '[]');
      return Array.isArray(value) ? value.filter(row => row && typeof row.kind === 'string' && typeof row.message === 'string') : [];
    } catch (_) { return []; }
  }
  function rememberDeveloperIssue(kind, message) {
    const key = developerKey();
    if (!key || typeof message !== 'string' || !message.trim()) return;
    try {
      const now = new Date().toISOString(), rows = developerObservations();
      const current = rows.find(row => row.kind === kind && row.message === message.trim());
      if (current) { current.count = (Number.isInteger(current.count) ? current.count : 1) + 1; current.last_at = now; }
      else rows.push({kind, message:message.trim().slice(0,1000), count:1, first_at:now, last_at:now});
      localStorage.setItem(key, JSON.stringify(rows));
    } catch (_) {}
  }
  function clearDeveloperIssues() {
    const key = developerKey();
    if (!key) return;
    try { localStorage.removeItem(key); } catch (_) {}
  }
  function notice(id, message) {
    text(id, message || '');
    $(id).classList.toggle('hidden', !message);
    if (id === 'draftNotice') $(id).classList.toggle('routine-notice', !!message && (message.includes('已保存') || message.includes('已恢复')));
  }
  function stance(value) { return value < 40 ? '偏防守' : value > 60 ? '偏进攻' : '均衡'; }
  function updateSliders() {
    AGES.forEach(age => {
      const value = Number($(age).value);
      text(age + 'Value', value + ' · ' + stance(value));
      $(age).setAttribute('aria-valuetext', value + '，' + stance(value));
    });
  }
  function usageConsent() {
    return document.querySelector('input[name="usage_auth"]:checked')?.value || '';
  }
  function authorizationReady() {
    return agents.some(agent => agent.id === ($('agent')?.value || '')) && ['allow','decline'].includes(usageConsent());
  }
  function authorizationConfirmed() {
    const auth = state?.usage_authorization;
    return !!auth && auth.agent === ($('agent')?.value || '') &&
      auth.authorized === (usageConsent() === 'allow');
  }
  function applyUsageAuthorization(auth) {
    if (!auth || typeof auth.agent !== 'string' || typeof auth.authorized !== 'boolean') return;
    if ($('agent') && agents.some(agent => agent.id === auth.agent)) $('agent').value = auth.agent;
    document.querySelectorAll('input[name="usage_auth"]').forEach(input => {
      input.checked = input.value === (auth.authorized ? 'allow' : 'decline');
    });
    renderAgentHelp();
  }
  function selection() {
    return {
      mode: document.querySelector('input[name="mode"]:checked')?.value || '',
      civilization: $('civilization').value,
      agent: $('agent')?.value || '',
      usage_authorized: usageConsent() === 'allow',
      script_name: $('scriptName').value,
      output_mode: document.querySelector('input[name="output_mode"]:checked')?.value || '',
      preferences: Object.fromEntries(AGES.map(age => [age, Number($(age).value)]))
    };
  }
  function applySelection(value) {
    document.querySelectorAll('input[name="mode"]').forEach(input => { input.checked = input.value === value.mode; });
    $('civilization').value = typeof value.civilization === 'string' ? value.civilization : '';
    if ($('agent')) $('agent').value = typeof value.agent === 'string' ? value.agent : '';
    document.querySelectorAll('input[name="usage_auth"]').forEach(input => {
      input.checked = typeof value.usage_authorized === 'boolean' &&
        input.value === (value.usage_authorized ? 'allow' : 'decline');
    });
    $('scriptName').value = typeof value.script_name === 'string' ? value.script_name : '';
    document.querySelectorAll('input[name="output_mode"]').forEach(input => {
      input.checked = input.value === value.output_mode;
    });
    AGES.forEach(age => { $(age).value = integer(value.preferences?.[age]) && value.preferences[age] <= 100 ? value.preferences[age] : 50; });
    updateSliders();
    updateCivilizationSelection(); showCivilization($('civilization').value || state?.civilizations[0]?.id); renderAgentHelp();
  }
  function editable() { return online && !busy && !stopped && state?.status === 'configuring'; }
  function validPreferences(p) {
    return p && Object.keys(p).length === AGES.length && AGES.every(age => integer(p[age]) && p[age] <= 100);
  }
  function validSelection(value) {
    return authorizationReady() && authorizationConfirmed() && MODES.includes(value.mode) && (state?.civilizations || []).length > 0 &&
      (value.civilization === 'auto' || state.civilizations.some(c => c.id === value.civilization)) &&
      /^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test(value.script_name) && OUTPUT_MODES.includes(value.output_mode) && validPreferences(value.preferences);
  }
  function draftKey() { return 'aoe2.web-author.draft.' + project; }
  function storageFailure() {
    storageAvailable = false;
    const message = '浏览器无法保存草稿。未提交的设置在关闭页面后可能丢失。';
    notice('draftNotice', message);
    rememberDeveloperIssue('storage_failure', message);
  }
  function saveDraft() {
    if (!editable() || !project) return;
    dirty = true;
    if (!storageAvailable) return;
    try {
      localStorage.setItem(draftKey(), JSON.stringify({schema: DRAFT_SCHEMA, project_id: project, step: wizardStep, value: selection()}));
      notice('draftNotice', '设置已保存。');
    } catch (_) { storageFailure(); }
  }
  function restoreDraft() {
    if (draftLoaded || !project || state.status !== 'configuring' || !agentsReady) return;
    draftLoaded = true;
    try {
      const raw = localStorage.getItem(draftKey());
      if (!raw) {
        applyUsageAuthorization(state.usage_authorization);
        return;
      }
      const draft = JSON.parse(raw), value = draft?.value;
      const allowedCiv = value?.civilization === '' || value?.civilization === 'auto' ||
        (state.civilizations || []).some(c => c.id === value?.civilization);
      if (![DRAFT_SCHEMA, 'aoe2-parameter-web-draft-v3', 'aoe2-parameter-web-draft-v2', 'aoe2-parameter-web-draft-v1'].includes(draft.schema) || draft.project_id !== project || !value ||
          (value.mode !== '' && !MODES.includes(value.mode)) || !allowedCiv ||
          typeof value.script_name !== 'string' || value.script_name.length > 48 || !validPreferences(value.preferences)) {
        notice('draftNotice', '这份浏览器草稿与当前资料不匹配，未恢复。请重新设置。');
        return;
      }
      applySelection(value);
      if (value.agent && !agents.some(agent => agent.id === value.agent)) $('agent').value = '';
      applyUsageAuthorization(state.usage_authorization);
      wizardStep = integer(draft.step) ? Math.min(draft.step, 3) : 0;
      while (wizardStep > 0 && !canVisit(wizardStep)) wizardStep--;
      dirty = true;
      notice('draftNotice', '已恢复设置。');
    } catch (error) {
      if (error instanceof SyntaxError) notice('draftNotice', '浏览器草稿无法读取，未恢复。请重新设置。');
      else storageFailure();
    }
  }
  function clearDraft() {
    if (!project) return;
    try { localStorage.removeItem(draftKey()); } catch (_) { storageAvailable = false; }
    dirty = false;
    notice('draftNotice', '');
  }
  function selectedCivValid() {
    const id = $('civilization').value;
    return (state?.civilizations || []).length > 0 && (id === 'auto' || state.civilizations.some(c => c.id === id));
  }
  function canVisit(step) {
    if (state && state.status !== 'configuring') return step === 4;
    const value = selection();
    if (step === 0) return true;
    if (!authorizationReady() || !authorizationConfirmed()) return false;
    if (step === 1) return true;
    if (!MODES.includes(value.mode)) return false;
    if (step === 2) return true;
    if (!selectedCivValid()) return false;
    if (step === 3) return true;
    return false;
  }
  function goStep(step, focus = true) {
    if (!canVisit(step) || step < 0 || step > 4 || busy) return;
    wizardStep = step;
    if (step === 3 && !$('scriptName').value) suggestName();
    saveDraft(); syncActions();
    if (focus) {
      $('configTitle').focus({preventScroll: true});
      $('configTitle').scrollIntoView({block: 'start', behavior: 'instant'});
    }
  }
  function renderSummary() {
    const value = state?.status === 'configuring' ? selection() : state?.request || selection();
    const civ = civData(value.civilization);
    const agent = agents.find(a => a.id === value.agent);
    const lines = [
      ['对局', MODE_NAMES[value.mode] || '尚未选择'],
      ['文明', value.civilization === 'auto' ? '由 AI 选择' : civ?.name || value.civilization || '尚未选择'],
      ['输出', value.output_mode === 'share_package' ? '分享脚本包' : value.output_mode === 'raw_scripts' ? '原生脚本' : '尚未选择']
    ];
    $('selectionSummary').replaceChildren();
    lines.forEach(([name, value]) => {
      const dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = name; dd.textContent = value; $('selectionSummary').append(dt, dd);
    });
  }
  function syncActions() {
    const locked = state && state.status !== 'configuring';
    document.body.classList.toggle('civilization-step', wizardStep === 2);
    document.body.classList.toggle('is-configuring', state?.status === 'configuring');
    $('configFields').disabled = !editable();
    if ($('agent')) $('agent').disabled = !editable() || state?.usage_authorization?.authorized === true || !!state?.usage_authorization?.revoked_at;
    $('startButton').disabled = !editable() || wizardStep !== 3 || !validSelection(selection());
    $('startButton').classList.toggle('hidden', wizardStep !== 3 || !!locked);
    text('startButton', busy ? '正在提交…' : '开始生成');
    $('startButton').setAttribute('aria-busy', String(busy));
    text('settingsState', state?.status === 'configuring' ? (dirty ? '草稿已保存' : '未保存草稿') : state ? '设置已锁定' : '正在读取');
    text('startHint', !online ? '连接中断，暂不能提交。' : '生成后不可修改本轮设置。');
    text('configTitle', STEP_NAMES[wizardStep]);
    text('stepEyebrow', '步骤 ' + (wizardStep + 1) + ' / 5');
    for (let step = 0; step < 5; step++) {
      const button = $('wizardNav' + step);
      $('wizardPanel' + step).hidden = wizardStep !== step;
      button.disabled = busy || !state || !canVisit(step);
      if (wizardStep === step) button.setAttribute('aria-current', 'step');
      else button.removeAttribute('aria-current');
      button.classList.toggle('complete', step < wizardStep);
    }
    const finalRunning = wizardStep === 4 && locked;
    $('reviewBeforeStart').hidden = !!locked;
    $('authorForm').classList.toggle('hidden', !!finalRunning);
    $('generationDashboard').hidden = !finalRunning;
    $('wizardActions').classList.toggle('hidden', !!finalRunning);
    $('previousStep').classList.toggle('hidden', wizardStep === 0);
    $('previousStep').disabled = busy || !online;
    $('nextStep').classList.toggle('hidden', wizardStep >= 3);
    $('nextStep').disabled = !editable() || (wizardStep === 0 ? !authorizationReady() : !canVisit(wizardStep + 1));
    text('nextStep', [authorizationConfirmed() ? '下一步' : '授权并继续', '下一步', '下一步', '', ''][wizardStep]);
    $('skipMetering').classList.toggle('hidden', wizardStep !== 0 || authorizationConfirmed());
    $('skipMetering').disabled = !editable() || !agentsReady;
    text('navigationHint', wizardStep === 1 && !MODES.includes(selection().mode) ? '请选择游戏模式' :
      wizardStep === 2 && !selectedCivValid() ? '请选择文明、AI 选择或随机文明' : '');
    document.querySelectorAll('[data-result]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.result === resultView)));
    ['progress', 'usage', 'report'].forEach(view => { $(view + 'Panel').hidden = resultView !== view; });
    renderMeterStatus(); renderSummary(); updateCivilizationSelection();
    $('generateReportButton').disabled = reportBusy || !online || !state || stopped;
    $('generateReportButton').setAttribute('aria-busy', String(reportBusy));
    text('generateReportButton', reportBusy ? '正在生成…' : '生成报告');
  }
  function renderMeterStatus() {
    const connection = state?.usage_connection || {};
    const labels = {NOT_AUTHORIZED:'等待授权', DISABLED:'本轮不计量', REVOKED:'计量已停止', RECORDING:'正在记录用量', LIMITED:'计量存在缺口', AWAITING_USAGE:'等待用量记录', CONNECTING:'Agent 正在接入'};
    text('meterStatus', labels[connection.status] || (state?.usage_authorization?.authorized ? 'Agent 正在接入' : '等待授权'));
    $('meterStatus').dataset.status = connection.status || 'NOT_AUTHORIZED';
    $('meterStatus').title = connection.reason || 'Token 采集状态';
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
      if (button.dataset.special === 'true') {
        button.hidden = false;
      } else {
        const civ = civData(button.dataset.civilization);
        button.hidden = ![civ?.name, civ?.name_en, civ?.id].some(value => String(value || '').toLocaleLowerCase().includes(term));
      }
      if (!button.hidden) visible++;
    });
    $('civilizationEmpty').classList.toggle('hidden', visible > 0 || !catalogReady);
  }

  async function api(path, options = {}) {
    const controller = new AbortController();
    const {timeoutMs = 8000, ...fetchOptions} = options;
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const response = await fetch(path, {
        ...fetchOptions, signal: controller.signal, cache: 'no-store',
        headers: {'Content-Type': 'application/json', ...(fetchOptions.headers || {})}
      });
      const data = await response.json();
      if (!response.ok) throw new Error(typeof data.message === 'string' ? data.message : typeof data.error === 'string' ? data.error : '操作失败（' + response.status + '）');
      return data;
    } finally { clearTimeout(timer); }
  }
  function validateState(next) {
    if (!next || typeof next !== 'object' || typeof next.project_id !== 'string' || !next.project_id ||
        typeof next.status !== 'string' || next.revision === undefined || !Array.isArray(next.civilizations)) {
      throw new Error('服务器状态不完整，已暂停提交。');
    }
    if (project && project !== next.project_id) {
      stopped = true;
      throw new Error('当前服务已切换项目，请刷新页面后继续；未自动提交任何设置。');
    }
  }
  function civData(id) {
    const basic = (state?.civilizations || []).find(c => c.id === id);
    if (!basic) return null;
    const details = catalog.find(c => c.id === id) || {};
    return {...basic, ...details, name: typeof details.name === 'string' && details.name.trim() ? details.name : basic.name};
  }
  function safeIcon(value) {
    return typeof value === 'string' && value.startsWith('/assets/civilizations/') && /^[a-z0-9_-]+[.]png$/i.test(value.slice('/assets/civilizations/'.length)) ? value : '';
  }
  function showCivilization(id) {
    previewCivilization = id;
    const selected = $('civilization').value;
    $('detailIcon').classList.add('hidden');
    $('detailSections').replaceChildren(); text('detailSource', '');
    if (!id || id === 'auto' || id === 'random') {
      const isAuto = id === 'auto', isRandom = id === 'random';
      text('detailName', isAuto ? 'AI 选择' : isRandom ? '随机文明' : '选择文明');
      text('detailEnglish', '');
      text('detailState', isAuto && selected === 'auto' ? '已选中' : isRandom ? '随机选择' : isAuto ? 'AI 选择' : '文明资料');
      text('detailDescription', isAuto ? '由 AI 根据当前对局与参数偏好选择文明。' :
        isRandom ? '从当前可选文明池随机选择一个文明。' : '点击盾徽选择文明。');
    } else {
      const civ = civData(id); if (!civ) return;
      text('detailName', civ.name); text('detailEnglish', civ.name_en || '');
      text('detailState', selected === id ? '已选中' : '预览 · 点击盾徽选中');
      text('detailDescription', civ.description || '文明资料暂不可用。');
      const icon = safeIcon(civ.icon);
      if (icon) {
        $('detailIcon').src = icon; $('detailIcon').classList.remove('hidden');
        $('detailIcon').onerror = () => $('detailIcon').classList.add('hidden');
      }
      [['文明加成', civ.bonuses], ['特色单位', civ.unique_units], ['特色科技', civ.unique_techs], ['团队加成', civ.team_bonus]].forEach(([label, values]) => {
        if (!Array.isArray(values) || !values.length) return;
        const section = document.createElement('section'), title = document.createElement('h4'), list = document.createElement('ul');
        section.className = 'detail-section'; title.textContent = label;
        values.forEach(value => {
          const content = typeof value === 'string' ? value : value && typeof value === 'object' ? [value.name, value.description].filter(Boolean).join('：') : '';
          if (content) { const li = document.createElement('li'); li.textContent = content; list.append(li); }
        });
        if (list.children.length) { section.append(title, list); $('detailSections').append(section); }
      });
      text('detailSource', typeof civ.source_note === 'string' ? civ.source_note : '资料仅供参考。');
    }
    document.querySelectorAll('.civilization-card').forEach(button => button.classList.toggle('previewing', button.dataset.civilization === id));
  }
  function updateCivilizationSelection() {
    const id = $('civilization').value;
    document.querySelectorAll('.civilization-card').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.civilization === id)));
    text('selectedCivilization', id === 'auto' ? '已选择：AI 选择' : id && civData(id) ? '已选中：' + civData(id).name + '' : '尚未选择文明');
    if (previewCivilization === id && id) text('detailState', id === 'auto' ? 'AI 选择' : '已选中');
  }
  function chooseCivilization(id) {
    if (!editable()) return;
    $('civilization').value = id; showCivilization(id); saveDraft(); syncActions();
  }
  function chooseRandomCivilization() {
    if (!editable()) return;
    const available = (state?.civilizations || []).filter(civ => typeof civ?.id === 'string' && civ.id);
    if (!available.length) return;
    const choice = available[Math.floor(Math.random() * available.length)];
    chooseCivilization(choice.id);
  }
  function renderCivilizations() {
    const signature = JSON.stringify([state.civilizations, catalog]);
    if (civilizationSignature === signature) return;
    civilizationSignature = signature;
    $('civilizationGrid').replaceChildren();
    const addSpecial = (id, label, mark) => {
      const button = document.createElement('button'), shield = document.createElement('span'), name = document.createElement('span');
      button.type = 'button'; button.className = 'civilization-card special-civilization-card';
      button.dataset.civilization = id; button.dataset.special = 'true';
      button.setAttribute('aria-pressed', 'false'); button.setAttribute('aria-label', label);
      shield.className = 'special-civ-shield'; shield.textContent = mark; shield.setAttribute('aria-hidden', 'true');
      name.className = 'civ-name'; name.textContent = label; button.append(shield, name);
      button.addEventListener('pointerenter', event => { if (event.pointerType === 'mouse') showCivilization(id); });
      button.addEventListener('focus', () => showCivilization(id));
      button.addEventListener('click', () => id === 'auto' ? chooseCivilization('auto') : chooseRandomCivilization());
      $('civilizationGrid').append(button);
    };
    addSpecial('auto', 'AI 选择', 'AI');
    addSpecial('random', '随机文明', '?');
    state.civilizations.forEach(basic => {
      if (typeof basic.id !== 'string' || typeof basic.name !== 'string') return;
      const civ = civData(basic.id), button = document.createElement('button'), name = document.createElement('span'), icon = safeIcon(civ.icon);
      button.type = 'button'; button.className = 'civilization-card'; button.dataset.civilization = civ.id;
      button.setAttribute('aria-pressed', 'false'); button.setAttribute('aria-label', civ.name);
      if (icon) {
        const img = document.createElement('img'); img.src = icon; img.alt = ''; img.width = 70; img.height = 70;
        img.addEventListener('error', () => {
          img.hidden = true;
          const fallback = document.createElement('span'); fallback.className = 'civ-fallback'; fallback.textContent = '—'; button.prepend(fallback);
          notice('civilizationAssetNotice', '部分盾徽暂不可用，文明名称与选择仍可使用。');
          rememberDeveloperIssue('civilization_asset', '部分文明盾徽加载失败。');
        }, {once:true});
        button.append(img);
      } else {
        const fallback = document.createElement('span'); fallback.className = 'civ-fallback'; fallback.textContent = '—'; button.append(fallback);
      }
      name.className = 'civ-name'; name.textContent = civ.name; button.append(name);
      button.addEventListener('pointerenter', event => { if (event.pointerType === 'mouse') showCivilization(civ.id); });
      button.addEventListener('focus', () => showCivilization(civ.id));
      button.addEventListener('click', () => chooseCivilization(civ.id));
      $('civilizationGrid').append(button);
    });
    if (!state.civilizations.length) text('civilizationGrid', '文明列表暂不可用，等待服务恢复。');
    text('contentScope', '标准版 · ' + state.civilizations.length + ' 个文明');
    if (!catalogReady) notice('civilizationAssetNotice', '文明资料暂不可用。');
    else notice('civilizationAssetNotice', '');
    updateCivilizationSelection(); showCivilization($('civilization').value || 'auto'); filterCivilizations();
  }
  function renderAgents() {
    const signature = JSON.stringify(agents);
    if (agentSignature === signature) return;
    agentSignature = signature;
    const previous = $('agent')?.value || '';
    $('agentOptions').replaceChildren();
    const wrapper = document.createElement('div'); wrapper.className = 'field agent-select-field';
    const label = document.createElement('label'); label.htmlFor = 'agent'; label.textContent = 'Agent';
    const select = document.createElement('select'); select.id = 'agent'; select.name = 'agent'; select.required = true; select.setAttribute('aria-describedby', 'agentHelp');
    select.append(new Option(agentsReady ? '请选择 AI' : 'AI 列表暂不可用', ''));
    agents.forEach(agent => { if (typeof agent.id === 'string' && typeof agent.label === 'string') select.append(new Option(agent.label, agent.id)); });
    const preferred = state?.usage_authorization?.agent || previous || state?.host_agent || 'auto';
    select.value = agents.some(agent => agent.id === preferred) ? preferred : agentsReady ? 'auto' : '';
    wrapper.append(label, select); $('agentOptions').append(wrapper);
    renderAgentHelp();
  }
  function renderAgentHelp() {
    const agent = agents.find(agent => agent.id === $('agent')?.value);
    let help = agent?.id === 'auto' ? '自动识别当前 Agent 和会话。' : '选择实际宿主，不启动或切换工具。';
    if (agent?.id === 'cursor') help += state?.usage_access?.cursor_admin_configured
      ? ' Team Usage API 已配置。'
      : ' Team Usage API 未配置；需其他真实 usage 来源。';
    text('agentHelp', agent ? help : '正在读取可用的 Agent…');
    const auth = state?.usage_authorization;
    text('authorizationStatus', auth?.revoked_at ? '已撤回授权，保留已有记录。' :
      authorizationConfirmed() ? auth.authorized ? '已授权，采集状态见顶部。' : '本轮不计量。' :
      '未授权');
  }

  function renderCivilizationDecision() {
    const actual = state.request?.civilization;
    const choice = state.civilization_selection?.choice;
    const visible = state.status !== 'configuring' && typeof actual === 'string' && actual !== 'auto' && !!actual;
    $('civilizationDecision').classList.toggle('hidden', !visible);
    if (!visible) return;
    const civilization = civData(actual);
    text('civilizationDecisionLabel', choice?.selected_by === 'user' ? '用户指定文明' : choice?.selected_by === 'ai' ? 'AI 已选文明' : '已选文明');
    text('civilizationDecisionName', civilization?.name || actual);
    text('civilizationDecisionReason', choice?.selected_by === 'user' ? '用户指定。' :
      typeof choice?.reason === 'string' && choice.reason.trim() ? choice.reason : '暂无选择说明。');
  }
  function renderBuild() {
    const build = state.build;
    const show = state.status === 'completed' && build && typeof build === 'object';
    $('buildResult').classList.toggle('hidden', !show);
    $('buildDetails').replaceChildren();
    if (!show) return;
    const fields = [
      ['输出', build.output_mode === 'share_package' ? '分享脚本包' : '原生脚本'],
      ['脚本名', build.script_name || state.request?.script_name],
      ['脚本文件', integer(build.script_files) ? build.script_files + ' 个 .per' : '—'],
      ['输出位置', build.package_file || build.script_root || build.path],
      ['答卷 SHA-256', build.answers_sha256 || build.parameter_sha256 || build.parameters_sha256],
      ['文件 SHA-256', build.package_sha256 || build.manifest_sha256]
    ];
    fields.forEach(([label, value]) => {
      if (typeof value !== 'string' || !value) return;
      const dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = label;
      if (label === '输出位置' && build.output_mode === 'share_package') {
        const link = document.createElement('a');
        link.href = '/api/delivery/download';
        link.download = build.package_name || (build.script_name || 'scripts') + '.zip';
        link.className = 'text-button delivery-download';
        link.textContent = '下载 ' + link.download;
        dd.append(link);
      } else {
        dd.textContent = value;
      }
      $('buildDetails').append(dt, dd);
    });
  }
  function renderState() {
    renderCivilizations(); renderAgents();
    const known = Object.hasOwn(STATUS, state.status);
    const label = state.status === 'completed' && state.build?.installable === false
      ? ['文件已生成', '模块文件暂不能直接安装，尚未进行游戏实测。']
      : known ? STATUS[state.status] : ['阶段未识别', '服务返回未知阶段，已暂停提交。'];
    text('statusBadge', label[0]); text('statusBanner', label[1]);
    $('statusBanner').hidden = !label[1];
    $('statusBadge').className = 'badge' + (state.status === 'completed' ? ' success' : state.status === 'invalid' ? ' warning' : '');
    text('projectLabel', '当前项目 · ' + project);
    if (state.status === 'configuring') {
      if (!draftLoaded && state.request) applySelection(state.request);
      restoreDraft();
    } else if (known) {
      clearDraft();
      const signature = JSON.stringify(state.request);
      if (signature !== lastRequestSignature && state.request) { applySelection(state.request); wizardStep = 4; lastRequestSignature = signature; }
    }
    const position = {configuring: 0, selecting: 1, authoring: 2, invalid: 3, ready: 3, rendering: 4, completed: 5}[state.status];
    ['stepConfig', 'stepSelect', 'stepAuthor', 'stepValidate', 'stepBuild'].forEach((id, index) => {
      $(id).className = position > index ? 'done' : position === index ? 'active' : '';
    });
    applyUsageAuthorization(state.usage_authorization);
    text('progressTitle', state.status === 'completed' ? '生成完成' : state.status === 'invalid' ? '参数修正' : '参数进度');
    const p = state.progress || {};
    const filled = integer(p.filled) ? p.filled : null, total = integer(p.total) && p.total > 0 ? p.total : null;
    text('fillCount', number(filled) + ' / ' + number(total) + ' 项参数');
    text('progressPercent', filled !== null && total !== null && filled <= total ? Math.floor(filled / total * 100) + '%' : '—');
    if (filled !== null && total !== null && filled <= total) {
      $('fillProgress').max = total; $('fillProgress').value = filled;
      $('fillProgress').setAttribute('aria-valuetext', '已填写 ' + filled + ' 项，共 ' + total + ' 项');
    } else {
      $('fillProgress').removeAttribute('value');
      $('fillProgress').setAttribute('aria-valuetext', '填写进度未知');
    }
    const errors = Array.isArray(p.errors) ? p.errors.length : integer(p.errors) ? p.errors : null;
    const validation = state.status === 'configuring' ? '尚未开始。' :
      state.status === 'selecting' ? '正在确定文明。' :
      state.status === 'authoring' ? '正在生成参数。' :
      state.status === 'invalid' ? '发现 ' + number(errors) + ' 项需要修正。' :
      ['ready', 'rendering', 'completed'].includes(state.status) ? '检查通过。' : '等待检查。';
    text('validationState', validation);
    renderCivilizationDecision(); renderBuild(); syncActions();
  }
  function tableCell(tag, value) {
    const element = document.createElement(tag); element.textContent = value;
    if (tag === 'th') element.scope = 'row';
    return element;
  }
  function renderUsage(report) {
    if (!report || typeof report !== 'object') return;
    lastUsage = report;
    const tokens = report.tokens || {}, time = report.time || {}, auto = report.auto_capture || {};
    text('usageState', {RUNNING: '记录中', COMPLETED: '已完成', SESSION_CLOSED: '已关闭', ABORTED: '已中止'}[report.state] || '等待用量记录');
    text('usageTokens', number(tokens.total_tokens)); text('usageElapsed', duration(time.elapsed_seconds));
    text('usageWork', duration(time.workflow_seconds)); text('usageUnobserved', duration(time.unobserved_seconds));
    const coverage = {
      NOT_CONNECTED: 'token 尚未记录。',
      PARTIAL: '当前仅显示已记录用量。',
      HOST_REPORTED_COMPLETE: '用量记录已完成。'
    }[report.coverage] || '当前仅显示已记录用量。';
    const captureLabel = {CONNECTED: '已连接用量采集', CONNECTED_BUILTIN: '已连接本地用量采集',
      CONNECTED_PARTIAL: '已连接部分采集', NOT_CONNECTED: '采集未连接', DISABLED: '自动用量采集已关闭',
      NO_BINDINGS: '尚未绑定用量会话', NO_BOUND_SESSIONS: '尚未观察到已绑定会话', DISCOVERING: '正在查找已绑定会话',
      NO_THREAD_ID: '未取得当前任务用量标识', THREAD_LOG_NOT_FOUND: '正在等待任务用量日志', LOG_UNAVAILABLE: '用量日志暂不可读',
      ROLLOUT_REPLACED: '用量日志发生变化', ERROR: '用量采集出现错误'}[auto.status];
    const connection = auto.connection && typeof auto.connection === 'object' ? auto.connection : {};
    const selectedAgent = agents.find(agent => agent.id === (auto.selected_agent || state?.request?.agent));
    const agentLabel = selectedAgent?.label || (auto.selected_agent || state?.request?.agent ? (auto.selected_agent || state.request.agent) : '未选择宿主');
    const message = typeof connection.message === 'string' ? connection.message : captureLabel || '等待采集连接信息';
    const detail = state?.usage_connection?.reason || message;
    text('usageCapture', 'Agent：' + agentLabel + ' · ' + detail);
    $('usageCapture').className = 'capture-status ' + (String(auto.status || '').startsWith('CONNECTED') ? 'connected' : 'attention');
    text('usageCoverage', coverage);
    $('usageGaps').replaceChildren();
    (Array.isArray(report.capture_gaps) ? report.capture_gaps : []).forEach(gap => {
      if (typeof gap?.message !== 'string') return;
      const li = document.createElement('li'); li.textContent = gap.message; $('usageGaps').append(li);
    });
    $('usageGaps').classList.toggle('hidden', !$('usageGaps').children.length);
    [['inputTokens','input_tokens'],['outputTokens','output_tokens'],['cacheTokens','cached_input_tokens'],
      ['cacheWriteTokens','cache_write_tokens'],['reasoningTokens','reasoning_tokens']].forEach(([id,key]) => text(id, finite(tokens[key]) ? number(tokens[key]) : '未提供'));
    renderTokenMix(tokens);
    $('usageStages').replaceChildren();
    const stages = Array.isArray(report.stages) ? report.stages : [];
    const stageTotal = stages.reduce((sum, stage) => sum + (finite(stage.total_tokens) && stage.total_tokens > 0 ? stage.total_tokens : 0), 0);
    stages.forEach(stage => {
      const row = document.createElement('tr'), tokenCell = document.createElement('td');
      const wrap = document.createElement('div'), bar = document.createElement('span'), fill = document.createElement('i'), value = document.createElement('span');
      wrap.className = 'stage-token'; bar.className = 'stage-bar'; bar.setAttribute('aria-hidden', 'true'); value.textContent = number(stage.total_tokens);
      const share = stageTotal > 0 && finite(stage.total_tokens) ? Math.max(0, stage.total_tokens) / stageTotal : 0;
      fill.style.width = (share * 100).toFixed(2) + '%';
      bar.append(fill); wrap.append(bar, value); tokenCell.append(wrap);
      const failures = document.createElement('td');
      failures.textContent = number(stage.action_failures) + ' / ' + number(stage.action_attempts);
      if (integer(stage.action_failures) && stage.action_failures > 0) failures.className = 'has-failures';
      row.append(tableCell('th', typeof stage.label === 'string' ? stage.label : '阶段未记录'), tokenCell,
        tableCell('td', duration(stage.elapsed_seconds)), failures);
      $('usageStages').append(row);
    });
    if (!stages.length) {
      const row = document.createElement('tr'), cell = tableCell('td', '尚无阶段报告。');
      cell.colSpan = 4; cell.className = 'empty-cell'; row.append(cell); $('usageStages').append(row);
    }
    renderModels(Array.isArray(report.by_model) ? report.by_model : [], tokens.total_tokens);
    const warn = value => integer(value) && value > 0;
    $('usageQuality').replaceChildren();
    [['请求', number(tokens.request_records)],
      ['累计用量区间', number(tokens.usage_interval_records)],
      ['聚合轮次', number(tokens.turn_records)],
      ['结果未知', number(tokens.unknown_outcome_records), warn(tokens.unknown_outcome_records) || tokens.outcome_complete === false],
      ['缺 usage', number(tokens.missing_usage_records), warn(tokens.missing_usage_records)],
      ['失败或取消消耗', number(tokens.failed_or_cancelled_tokens), warn(tokens.failed_or_cancelled_tokens)],
      ['重试', number(tokens.retry_records) + ' 条 · ' + number(tokens.retry_tokens)],
      ['配置耗时', duration(time.configuration_seconds)],
      ['工具执行合计', duration(time.tool_seconds)]
    ].forEach(([label, value, attention]) => {
      const item = document.createElement('div'), dt = document.createElement('dt'), dd = document.createElement('dd');
      dt.textContent = label; dd.textContent = value;
      if (attention) item.className = 'attention';
      item.append(dt, dd); $('usageQuality').append(item);
    });
    text('usageBreakdown', '重试消耗已计入总量；工具执行时间可能与流程时间重叠，不额外相加。' +
      (tokens.detail_complete && Object.values(tokens.detail_complete).some(value => value === false) ? ' 部分 token 数据未记录。' : ''));
  }
  function percent(part, whole) {
    return finite(part) && finite(whole) && whole > 0 ? Math.round(part / whole * 1000) / 10 + '%' : '';
  }
  function renderTokenMix(tokens) {
    const input = finite(tokens.input_tokens) ? Math.max(0, tokens.input_tokens) : null;
    const output = finite(tokens.output_tokens) ? Math.max(0, tokens.output_tokens) : null;
    const cached = input !== null && finite(tokens.cached_input_tokens) ? Math.min(input, Math.max(0, tokens.cached_input_tokens)) : 0;
    const reasoning = output !== null && finite(tokens.reasoning_tokens) ? Math.min(output, Math.max(0, tokens.reasoning_tokens)) : 0;
    const whole = (input || 0) + (output || 0);
    const segments = {'mix-input': (input || 0) - cached, 'mix-cache': cached, 'mix-output': (output || 0) - reasoning, 'mix-reasoning': reasoning};
    Object.entries(segments).forEach(([name, value]) => {
      $('tokenMix').querySelector('.' + name).style.flexGrow = whole > 0 ? String(value) : '0';
    });
    $('tokenMix').classList.toggle('is-empty', whole <= 0);
    $('tokenMix').setAttribute('aria-label', whole > 0
      ? 'Token 构成：输入 ' + percent(input, whole) + '，输出 ' + percent(output, whole)
      : 'Token 构成暂无数据');
    text('inputShare', input !== null ? percent(input, whole) && '占输入+输出 ' + percent(input, whole) : '');
    text('outputShare', output !== null ? percent(output, whole) && '占输入+输出 ' + percent(output, whole) : '');
    text('cacheShare', finite(tokens.cached_input_tokens) && input ? '占输入 ' + percent(tokens.cached_input_tokens, input) : '');
    text('cacheWriteShare', finite(tokens.cache_write_tokens) && input ? '占输入 ' + percent(tokens.cache_write_tokens, input) : '');
    text('reasoningShare', finite(tokens.reasoning_tokens) && output ? '占输出 ' + percent(tokens.reasoning_tokens, output) : '');
  }
  function renderModels(models, total) {
    $('usageModels').replaceChildren();
    if (!models.length) {
      const empty = document.createElement('p'); empty.className = 'field-help'; empty.textContent = '模型用量尚未采集。';
      $('usageModels').append(empty); return;
    }
    models.forEach(model => {
      const row = document.createElement('div'), name = document.createElement('span'), value = document.createElement('strong');
      const bar = document.createElement('span'), fill = document.createElement('i');
      row.className = 'model-row'; name.className = 'model-name'; bar.className = 'stage-bar'; bar.setAttribute('aria-hidden', 'true');
      name.textContent = typeof model.model === 'string' && model.model ? model.model : '模型未记录';
      value.textContent = number(model.total_tokens);
      fill.style.width = finite(model.total_tokens) && finite(total) && total > 0 ? Math.min(100, model.total_tokens / total * 100).toFixed(2) + '%' : '0%';
      bar.append(fill); row.append(name, value, bar); $('usageModels').append(row);
    });
  }
  async function doRefresh() {
    const results = await Promise.allSettled([api('/api/state'), api('/api/author/usage'),
      catalogReady ? Promise.resolve({civilizations:catalog}) : api('/api/civilizations'),
      agentsReady ? Promise.resolve({agents}) : api('/api/agents')]);
    if (results[2].status === 'fulfilled' && Array.isArray(results[2].value.civilizations)) { catalog = results[2].value.civilizations; catalogReady = true; }
    else if (!catalogReady && project) rememberDeveloperIssue('civilization_catalog', results[2].reason?.message || '文明资料读取失败。');
    if (results[3].status === 'fulfilled' && Array.isArray(results[3].value.agents)) { agents = results[3].value.agents; agentsReady = true; }
    else if (!agentsReady && project) rememberDeveloperIssue('agent_catalog', results[3].reason?.message || 'AI 列表读取失败。');
    try {
      if (results[0].status === 'fulfilled') {
        validateState(results[0].value);
        state = results[0].value; project = state.project_id; online = true;
        text('connection', '已连接'); $('connection').className = 'connection online';
        if (networkError) { notice('errorNotice', ''); networkError = false; }
        renderState();
      } else {
        online = false; networkError = true;
        const message = '连接中断，正在重试。';
        text('connection', '连接中断'); $('connection').className = 'connection offline';
        notice('errorNotice', message);
        rememberDeveloperIssue('state_refresh', results[0].reason?.message || message);
        syncActions();
      }
      if (results[1].status === 'fulfilled') renderUsage(results[1].value);
      else if (results[0].status === 'fulfilled' && results[0].value.usage) renderUsage(results[0].value.usage);
      else {
        text('usageState', '用量暂不可用');
        text('usageCoverage', '暂时无法读取用量。');
        rememberDeveloperIssue('usage_refresh', results[1].reason?.message || '用量读取失败。');
      }
    } catch (error) {
      online = false; networkError = !stopped;
      text('connection', stopped ? '项目已变更' : '状态读取失败'); $('connection').className = 'connection offline';
      notice('errorNotice', error.message); rememberDeveloperIssue('state_validation', error.message); syncActions();
    }
  }
  function refresh() {
    if (stopped) return Promise.resolve();
    if (refreshPromise) return refreshPromise;
    refreshPromise = doRefresh().finally(() => { refreshPromise = null; });
    return refreshPromise;
  }
  document.querySelectorAll('.wizard-nav button').forEach(button => button.addEventListener('click', () => goStep(Number(button.dataset.step))));
  $('previousStep').addEventListener('click', () => goStep(wizardStep - 1));
  async function authorize(allowed, advance = true) {
    if (!online || busy || stopped || !state || (!advance && !state.usage_authorization?.authorized)) return;
    if (advance && !editable()) return;
    busy = true; syncActions(); notice('errorNotice', '');
    try {
      if (refreshPromise) await refreshPromise;
      const agent = state.usage_authorization?.authorized ? state.usage_authorization.agent : $('agent')?.value;
      const next = await api('/api/usage/authorize', {method:'POST', body:JSON.stringify({
        project_id:project, expected_revision:state.revision, agent, usage_authorized:allowed
      }), timeoutMs:30000});
      validateState(next); state = next;
      applyUsageAuthorization(next.usage_authorization);
      if (advance) wizardStep = 1;
      if (next.usage) renderUsage(next.usage);
    } catch (error) {
      const message = error.name === 'AbortError' ? '未收到授权回执，正在核对状态；不会重复开始创作。' : error.message;
      notice('errorNotice', message); rememberDeveloperIssue('usage_authorization', message);
    } finally {
      busy = false; saveDraft(); syncActions();
    }
  }
  $('nextStep').addEventListener('click', () => {
    if (wizardStep !== 0) { goStep(wizardStep + 1); return; }
    if (authorizationConfirmed()) goStep(1);
    else authorize(true);
  });
  $('skipMetering').addEventListener('click', () => authorize(false));
  $('revokeUsage').addEventListener('click', () => authorize(false, false));
  $('suggestName').addEventListener('click', () => { suggestName(); syncActions(); });
  $('civilizationSearch').addEventListener('input', filterCivilizations);
  document.querySelectorAll('[data-result]').forEach(button => button.addEventListener('click', () => {
    resultView = button.dataset.result; syncActions();
  }));
  $('civilizationGrid').addEventListener('pointerleave', () => showCivilization(document.activeElement?.dataset.civilization || $('civilization').value || null));
  $('civilizationGrid').addEventListener('keydown', event => {
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', 'Home', 'End'].includes(event.key)) return;
    const buttons = [...$('civilizationGrid').querySelectorAll('button:not([hidden])')], current = buttons.indexOf(document.activeElement);
    if (current < 0) return;
    event.preventDefault();
    const columns = getComputedStyle($('civilizationGrid')).gridTemplateColumns.split(' ').length;
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : Math.max(0, Math.min(buttons.length - 1, current + ({ArrowLeft:-1,ArrowRight:1,ArrowUp:-columns,ArrowDown:columns}[event.key])));
    buttons[next]?.focus();
  });
  $('scriptName').addEventListener('blur', () => {
    const invalid = $('scriptName').value !== '' && !/^[A-Za-z][A-Za-z0-9_-]{0,47}$/.test($('scriptName').value);
    $('scriptName').setAttribute('aria-invalid', String(invalid));
    text('nameHelp', invalid ? '名称无效：字母开头；仅限字母、数字、_、-，最多 48 字符。' : '字母开头；仅限字母、数字、_、-，最多 48 字符。');
  });
  $('authorForm').addEventListener('input', () => { updateSliders(); saveDraft(); syncActions(); });
  $('authorForm').addEventListener('change', () => { renderAgentHelp(); saveDraft(); syncActions(); });
  $('resetPreferences').addEventListener('click', () => {
    if (!editable()) return;
    AGES.forEach(age => { $(age).value = 50; }); updateSliders(); saveDraft(); syncActions();
  });
  $('generateReportButton').addEventListener('click', async () => {
    if (reportBusy || !online || !state || !project || stopped) return;
    reportBusy = true; syncActions(); text('reportState', '正在生成…');
    try {
      const feedback = $('reportFeedback').value.trim();
      const result = await api('/api/report/generate', {method:'POST', body:JSON.stringify({
        project_id:project, feedback, browser_observations:developerObservations()
      })});
      $('reportOutput').value = typeof result.markdown === 'string' ? result.markdown : '';
      $('reportResult').classList.remove('hidden');
      $('downloadReportLink').href = result.download_url;
      $('downloadReportLink').download = result.markdown_download_name || 'aoe2-creation-report.md';
      $('downloadDetailsLink').href = result.details_url;
      $('downloadDetailsLink').download = result.technical_download_name || 'aoe2-technical-details.md';
      $('reportFeedback').value = ''; clearDeveloperIssues();
      text('reportState', '已生成 Markdown · ' + number(result.issue_count) + ' 个问题/提醒 · ' + number(result.feedback_count) + ' 条反馈');
    } catch (error) {
      const message = error.name === 'AbortError' ? '报告生成超时，请重试。' : error.message;
      text('reportState', message); rememberDeveloperIssue('report_generation', message);
    } finally {
      reportBusy = false; syncActions();
    }
  });
  $('copyReportButton').addEventListener('click', async () => {
    const value = $('reportOutput').value;
    if (!value) return;
    try {
      await navigator.clipboard.writeText(value);
      text('reportState', '已复制。');
    } catch (_) {
      $('reportOutput').focus(); $('reportOutput').select();
      text('reportState', '已选中报告内容，请手动复制。');
    }
  });
  $('refreshButton').addEventListener('click', () => { if (!stopped) { notice('errorNotice', ''); refresh(); } });
  $('authorForm').addEventListener('submit', async event => {
    event.preventDefault();
    if (wizardStep !== 3) return; // Enter in an earlier step must never grant consent or start creation.
    const value = selection();
    if (!editable() || !validSelection(value)) return;
    busy = true; syncActions(); notice('errorNotice', '');
    try {
      if (refreshPromise) await refreshPromise;
      await api('/api/start', {method: 'POST', body: JSON.stringify({project_id:project, expected_revision: state.revision, ...value}), timeoutMs:30000});
      clearDraft();
    } catch (error) {
      const message = error.name === 'AbortError' ? '提交超时，正在刷新状态。' : error.message;
      notice('errorNotice', message); rememberDeveloperIssue('start_submit', message);
    } finally {
      if (refreshPromise) await refreshPromise;
      await refresh();
      busy = false;
      syncActions();
    }
  });
  window.addEventListener('beforeunload', event => {
    if (dirty && !storageAvailable && state?.status === 'configuring') { event.preventDefault(); event.returnValue = ''; }
  });
  updateSliders();
  refresh();
  setInterval(() => { if (!busy) refresh(); }, 3000);
})();
